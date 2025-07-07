#coding:utf-8

import asyncio
import re
from pathlib import Path
from typing import List, Tuple
import subprocess
import logging
import string

import ollama

class SubtitleTranslator:
    def __init__(self, input_file: str, output_file: str, model_type: str, chunk_size: int = 30, max_concurrent: int = 10, context_size: int = 3, split_retry: int = 3, keep_punctuation: bool = False):
        self.input_file = Path(input_file)
        self.output_file = Path(output_file)
        self.model_type = model_type
        self.chunk_size = chunk_size
        self.max_concurrent = max_concurrent
        self.context_size = context_size
        self.split_retry = split_retry
        self.keep_punctuation = keep_punctuation

        self.ollama_client = ollama.AsyncClient()
        
        # 添加缓存相关的属性
        self.cache_dir = Path(".translate_cache")
        self.cache_dir.mkdir(exist_ok=True)
        self.cache_file = self.cache_dir / f"{self.input_file.stem}.cache"
        self.translation_cache = self._load_cache()

        self.prompt_template = """
任务描述：
你将担任字幕翻译助手，为一段视频的字幕文本进行翻译。请确保翻译内容符合以下要求：
1 时间线对齐：
    - 每段字幕的翻译内容必须与其对应的时间标记严格匹配，绝不能合并或拆分其他时间段的内容。
    - 时间线中的内容无论是否连贯，都必须逐一翻译，绝对不能跳过或调整顺序。
2 翻译准确性：
    - 精确传达原文含义，包括语境、语气和文化背景。
    - 保持目标语言的自然流畅和专业表达。
3 格式要求：
    - 保持原始字幕文件的时间标记格式（如 00:00:05,000 --> 00:00:07,000）。
    - 每段字幕不得超过两行，每行尽量不超过 42 个字符，确保字幕易读。
4 内容对齐：
    - 翻译时严格按照原文的编号顺序进行。
    - 不得将其他时间标记段的内容合并到当前段。即使语义不完整，也必须翻译当前段内容。

参考术语表：
   - Source Viewer: 源片段检视器
   - Timeline Viewer: 时间线检视器
   - Bin: 媒体夹
   - Smart Bins: 智能媒体夹
   - Full extent zoom: 全览缩放
   - Detail zoom: 细节缩放
   - Custum zoom: 自定缩放


输入格式：
字幕文件将以以下格式提供：

1
00:00:05,000 --> 00:00:07,000
Hello, how are you?

2
00:00:07,500 --> 00:00:10,000
I'm fine, thank you!

输出格式：
保持原始时间线和格式，仅替换为目标语言内容，例如：

1
00:00:05,000 --> 00:00:07,000
你好，你怎么样？

2
00:00:07,500 --> 00:00:10,000
我很好，谢谢！

注意事项：
- 不要对时间线和数字编号进行更改。
- 遇到无法翻译的词语，请标记为 [UNTRANSLATABLE]，并保留原文。

以下是字幕文件内容，请开始翻译：
{content}

"""
        self.quality_check_prompt = """

原文：
{source}

翻译：
{translation}

字幕翻译检查任务

任务目标：

你将作为字幕翻译质量检查助手，逐句检查翻译内容是否与原文准确匹配，并根据以下评分标准给出总分（满分 10 分）。
特别注意： 如发现字幕错乱（即字幕内容与时间线不匹配或有合并/错位），评分直接小于 5 分。

评分标准：

1. 字幕编号和时间线（2 分）：
  - 编号递增且无重复或跳号。
  - 错误例子：编号跳过、重复出现。
  - 每处错误扣 0.5 分，最多扣 1 分。
  - 时间线格式正确，且时间段无重叠。
  - 错误例子：时间段格式不符，时间线段重叠。
  - 每处错误扣 0.5 分，最多扣 1 分。

2. 翻译内容准确性（3 分）：
  - 翻译内容语义是否逐句与原文匹配，且是否完整无缺失。
  - 错位扣分规则：
  - 翻译内容与原文时间线错位或合并，每处扣 1 分，若错位影响后续翻译，额外扣 1 分。
  - 严重错乱情况：
  - 如果发现翻译段落与原文多处错乱或完全失去对齐，直接降至 小于 5 分。

3. 翻译与时间线对齐（5 分）：
  - 严格对齐：
  - 翻译必须严格与对应时间线匹配，无错位、无合并。
  - 错乱情况直接导致评分低于 5 分。
  - 逻辑连贯性：
  - 翻译段落之间内容应保持逻辑连贯，若因错乱造成逻辑断裂，额外扣 1 分。

评分规则：
  - 无错乱，且翻译完整准确：
  - 根据具体错误，按扣分规则计算总分，最高得 10 分。
  - 有错乱（任何错位或合并）：
  - 评分直接降至小于 5 分。
  - 错误轻微但存在错乱：4-5 分。
  - 错误严重且多处错乱：1-3 分。

按以下格式返回，只返回分数和问题,其他任何内容都不要返回。

<score>分数</score>
<suggestion>
简短的评估问题阐述
</suggestion>
"""

    def _load_cache(self) -> dict:
        """加载翻译缓存"""
        if self.cache_file.exists():
            try:
                import json
                return json.loads(self.cache_file.read_text(encoding='utf-8'))
            except Exception as e:
                print(f"加载缓存失败: {e}")
                return {}
        return {}

    def _save_cache(self):
        """保存翻译缓存"""
        try:
            import json
            self.cache_file.write_text(
                json.dumps(self.translation_cache, ensure_ascii=False, indent=2),
                encoding='utf-8'
            )
        except Exception as e:
            print(f"保存缓存失败: {e}")

    def _get_cache_key(self, text: str) -> str:
        """生成缓存键"""
        import hashlib
        return hashlib.md5(text.encode('utf-8')).hexdigest()

    def parse_subtitle(self, content: str) -> List[Tuple[str, str, str]]:
        """解析字幕文件，返回 [(序号, 时间戳, 文本内容)]"""
        # 移除 BOM 标记（如果存在）
        content = content.strip('\ufeff')
        
        # 标准化换行符并移除多余的空白字符
        content = content.replace('\r\n', '\n').replace('\r', '\n')
        content = re.sub(r'\n\s+\n', '\n\n', content)
        content = content.strip()
        
        # 更简单的解析方式
        result = []
        blocks = content.split('\n\n')
        invalid_blocks = []
        for block in blocks:
            if not block.strip():
                continue
                
            lines = block.strip().split('\n')
            if len(lines) >= 3:
                number = lines[0].strip()
                timestamp = lines[1].strip()
                text = '\n'.join(lines[2:]).strip()
                
                # 验证时间戳格式
                if re.match(r'\d{2}:\d{2}:\d{2},\d{3}\s*-->\s*\d{2}:\d{2}:\d{2},\d{3}', timestamp):
                    result.append((number, timestamp, text))
                else:
                    invalid_blocks.append(f"无效的时间戳格式: {block}")
            else:
                invalid_blocks.append(f"无效的字幕块: {block}")
        
        if invalid_blocks:
            error_msg = "\n".join(invalid_blocks)
            raise ValueError(f"字幕解析错误:\n{error_msg}")
            
        if not result:
            raise ValueError(f"解析结果为空，原文:\n{content}")
            
        return result

    def validate_format(self, translated_text: str) -> bool:
        """验证翻译后的文本是否符合字幕格式"""
        try:
            parsed = self.parse_subtitle(translated_text)
            if not parsed:
                logging.warning("解析结果为空")
                logging.warning(f"翻译返回内容:\n{translated_text}")
                return False
                
            for num, timestamp, text in parsed:
                if not num.strip() or not timestamp.strip() or not text.strip():
                    logging.warning(f"字幕项内容不完整: 序号={num}, 时间戳={timestamp}, 文本={text}")
                    return False
            return True
        except Exception as e:
            logging.warning(f"字幕解析失败: {str(e)}")
            logging.warning(f"翻译返回内容:\n{translated_text}")
            return False

    async def check_translation_quality(self, source_text: str, translated_text: str) -> Tuple[float, str]:
        """使用 LLM 评估翻译质量并获取修改建议"""
        try:
            print(f"正在进行翻译质量评估...")
            
            prompt = self.quality_check_prompt.format(
                source=source_text,
                translation=translated_text
            )
            
            # process = await asyncio.create_subprocess_exec(
            #     'guru',
            #     '--renderer', 'text',
            #     '-n',
            #     '--chatgpt.stream=false',
            #     '--chatgpt.temperature=1.3',
            #     '--chatgpt.max_tokens=8192',
            #     prompt,
            #     stdin=asyncio.subprocess.PIPE,
            #     stdout=asyncio.subprocess.PIPE,
            #     stderr=asyncio.subprocess.PIPE
            # )

            try:
                stdout = await self.ollama_client.chat(
                    model=self.model_type,
                    messages=[
                        {
                            'role': 'user',
                            'content': prompt,
                        },
                    ],
                    options={
                        'temperature': 1.3,
                        'num_predict': 8192,
                    },
                    stream=False
                )
            except Exception as e:
                print("质量评估失败!")
                raise Exception(f"质量评估命令执行失败: {e}")
            
            # stdout, stderr = await process.communicate()
            
            # if process.returncode != 0:
            #     print("质量评估失败!")
            #     raise Exception(f"质量评估命令执行失败: {stderr.decode('utf-8')}")
            
            # response = stdout.decode('utf-8').strip()

            response = stdout['message']['content'].strip()
            
            # 解析评分和建议
            score_match = re.search(r'<score>(.*?)</score>', response)
            suggestion_match = re.search(r'<suggestion>(.*?)</suggestion>', response, re.DOTALL)
            
            score = 0.0
            suggestion = ""
            
            if score_match:
                try:
                    score = float(score_match.group(1))
                except ValueError:
                    print(f"无法解析评分结果: {score_match.group(1)}")
            
            if suggestion_match:
                suggestion = suggestion_match.group(1).strip()
            
            print(f"质量评估得分: {score}/10 {'✓' if score >= 5.0 else '✗'}")
            if score < 8.0 and suggestion:
                print("修改建议:")
                print(suggestion)
            
            return score, suggestion
                
        except Exception as e:
            print(f"质量评估过程出错: {str(e)}")
            logging.error(f"质量评估失败: {str(e)}")
            return 0.0, ""

    def _remove_ending_punctuation(self, text):
        """去除文本末尾的单个标点符号,保留需要成对的标点"""
        # 定义行末可以去除的单个标点符号
        single_punctuation = '。，？！、；：'
        
        # 如果文本末尾是单个标点,则去除
        if text and text[-1] in single_punctuation:
            return text[:-1]
        return text

    def _process_translation(self, text):
        """处理翻译文本，根据设置决定是否保留标点"""
        if not self.keep_punctuation:
            original_text = text
            text = self._remove_ending_punctuation(text)
        return text

    def _process_subtitle_blocks(self, subtitles: List[Tuple[str, str, str]]) -> List[Tuple[str, str, str]]:
        """处理字幕块的标点符号"""
        processed = []
        for num, timestamp, text in subtitles:
            processed_text = self._process_translation(text)
            processed.append((num, timestamp, processed_text))
        return processed

    async def translate_chunk(self, chunk: List[Tuple[str, str, str]], all_subtitles: List[Tuple[str, str, str]], depth: int = 0) -> str:
        """翻译一个字幕块，包含上下文"""
        start_num = chunk[0][0]
        end_num = chunk[-1][0]
        print(f"开始翻译字幕块 {start_num}-{end_num} (深度: {depth})")

        chunk_start_idx = next(i for i, (num, _, _) in enumerate(all_subtitles) if num == start_num)
        
        max_retries = 10
        last_suggestion = ""
        
        for attempt in range(max_retries):
            current_context_size = self.context_size + attempt
            print(f"尝试使用上下文大小: {current_context_size}")
            
            # 检查是否需要拆分任务
            if attempt > 0 and attempt % self.split_retry == 0 and len(chunk) > 1:
                print(f"第 {attempt} 次重试，拆分任务...")
                mid = len(chunk) // 2
                first_half = chunk[:mid]
                second_half = chunk[mid:]
                
                try:
                    print(f"处理第一部分: {first_half[0][0]}-{first_half[-1][0]} ({len(first_half)}条)")
                    first_result = await self.translate_chunk(first_half, all_subtitles, depth + 1)
                    first_subtitles = self.parse_subtitle(first_result)
                    print(f"第一部分翻译完成，返回 {len(first_subtitles)} 条字幕")
                    
                    print(f"处理第二部分: {second_half[0][0]}-{second_half[-1][0]} ({len(second_half)}条)")
                    second_result = await self.translate_chunk(second_half, all_subtitles, depth + 1)
                    second_subtitles = self.parse_subtitle(second_result)
                    print(f"第二部分翻译完成，返回 {len(second_subtitles)} 条字幕")
                    
                    # 合并结果时，只保留各自部分的核心内容
                    if first_result and second_result:
                        # 获取第一部分的字幕
                        first_blocks = first_result.rstrip().split('\n\n')
                        # 获取第二部分的字幕
                        second_blocks = second_result.lstrip().split('\n\n')
                        
                        print("合并前检查:")
                        print(f"第一部分字幕块数: {len(first_blocks)}")
                        print(f"第二部分字幕块数: {len(second_blocks)}")
                        
                        # 根据原始chunk的序号筛选需要的字幕块
                        first_nums = {num for num, _, _ in first_half}
                        second_nums = {num for num, _, _ in second_half}
                        
                        # 只保留属于当前部分的字幕块
                        filtered_first = []
                        filtered_second = []
                        
                        for block in first_blocks:
                            lines = block.split('\n')
                            if len(lines) >= 1 and lines[0].strip() in first_nums:
                                filtered_first.append(block)
                            
                        for block in second_blocks:
                            lines = block.split('\n')
                            if len(lines) >= 1 and lines[0].strip() in second_nums:
                                filtered_second.append(block)
                        
                        print(f"过滤后第一部分字幕块数: {len(filtered_first)}")
                        print(f"过滤后第二部分字幕块数: {len(filtered_second)}")
                        
                        # 合并过滤后的结果
                        combined_result = '\n\n'.join(filtered_first + filtered_second)
                    else:
                        combined_result = first_result or second_result
                    
                    # 验证合并后的结果
                    try:
                        merged_subtitles = self.parse_subtitle(combined_result)
                        print(f"合并后总字幕数: {len(merged_subtitles)}, 期望数量: {len(chunk)}")
                        
                        if len(merged_subtitles) != len(chunk):
                            print("字幕数量不匹配，显示合并结果的前后几行:")
                            lines = combined_result.split('\n')
                            print("前5行:")
                            print('\n'.join(lines[:5]))
                            print("后5行:")
                            print('\n'.join(lines[-5:]))
                            raise ValueError(f"合并结果验证失败: 期望 {len(chunk)} 条字幕，实际得到 {len(merged_subtitles)} 条")
                        
                        # 验证序号的连续性
                        for i, (num, _, _) in enumerate(merged_subtitles):
                            expected_num = str(int(chunk[i][0]))
                            if num != expected_num:
                                raise ValueError(f"序号不匹配: 期望 {expected_num}，实际得到 {num}")
                                
                    except Exception as e:
                        logging.error(f"合并结果验证失败: {str(e)}")
                        raise
                    
                    return combined_result
                    
                except Exception as e:
                    logging.error(f"拆分任务处理失败: {str(e)}")
                    # 打印更多错误信息
                    import traceback
                    logging.error(traceback.format_exc())
                    continue
            
            # 构建包含上下文的字幕块
            context_start = max(0, chunk_start_idx - current_context_size)
            context_end = min(len(all_subtitles), chunk_start_idx + len(chunk) + current_context_size)
            context_chunk = all_subtitles[context_start:context_end]
            
            # 生成带上下文的字幕文本
            subtitle_text = '\n\n'.join(
                f'{num}\n{timestamp}\n{text}' 
                for num, timestamp, text in context_chunk
            )
            
            # 检查缓存
            cache_key = self._get_cache_key(subtitle_text)
            if cache_key in self.translation_cache:
                print(f"使用缓存的翻译结果 {start_num}-{end_num}")
                cached_text = self.translation_cache[cache_key]
                
                try:
                    cached_subtitles = self.parse_subtitle(cached_text)
                    # 对缓存的结果也应用标点处理
                    processed_subtitles = self._process_subtitle_blocks(cached_subtitles)
                    
                    context_prefix_size = min(current_context_size, chunk_start_idx)
                    if len(context_chunk) > len(chunk):
                        result_subtitles = processed_subtitles[context_prefix_size:len(processed_subtitles)-min(current_context_size, len(all_subtitles)-context_end+1)]
                    else:
                        result_subtitles = processed_subtitles
                        
                    result_text = '\n\n'.join(
                        f'{num}\n{timestamp}\n{text}' 
                        for num, timestamp, text in result_subtitles
                    )
                    return result_text
                except Exception as e:
                    logging.warning(f"处理缓存结果失败: {str(e)}")
                    del self.translation_cache[cache_key]
                    self._save_cache()

            try:
                # 在提示模板中加入上一次的修改建议
                full_prompt = self.prompt_template.format(content=subtitle_text)
                if last_suggestion:
                    full_prompt = f"""
{self.prompt_template.format(content=subtitle_text)}

参考以下修改建议进行优化：
{last_suggestion}
"""
                
                # process = await asyncio.create_subprocess_exec(
                #     'guru',
                #     '--renderer', 'text',
                #     '-n',
                #     '--chatgpt.stream=false',
                #     '--chatgpt.temperature=1.3',
                #     '--chatgpt.max_tokens=8192',
                #     full_prompt,
                #     stdin=asyncio.subprocess.PIPE,
                #     stdout=asyncio.subprocess.PIPE,
                #     stderr=asyncio.subprocess.PIPE
                # )

                try:
                    stdout = await self.ollama_client.chat(
                        model=self.model_type,
                        messages=[
                            {
                                'role': 'user',
                                'content': full_prompt,
                            },
                        ],
                        options={
                            'temperature': 1.3,
                            'num_predict': 8192,
                        },
                        stream=False
                    )
                except Exception as e:
                    raise Exception(f"翻译命令执行失败: {e}")
                
                # stdout, stderr = await process.communicate(subtitle_text.encode('utf-8'))
                
                # if process.returncode != 0:
                #     raise Exception(f"翻译命令执行失败: {stderr.decode('utf-8')}")
                
                # 处理翻译返回的文本，去除每行末尾的空白字符
                # translated_text = stdout.decode('utf-8')
                translated_text = stdout['message']['content']
                translated_text = '\n'.join(line.rstrip() for line in translated_text.splitlines())
                
                # 验证翻译结果格式
                if not self.validate_format(translated_text):
                    logging.warning(f"翻译块 {start_num}-{end_num} 第 {attempt + 1} 次尝试的结果格式无效")
                    continue
                    
                # 验证翻译结果的字幕数量是否匹配
                translated_subtitles = self.parse_subtitle(translated_text)
                expected_size = len(context_chunk)
                if len(translated_subtitles) != expected_size:
                    logging.warning(f"翻译块 {start_num}-{end_num} 第 {attempt + 1} 次尝试的字幕数量不匹配 (上下文大小: {current_context_size})")
                    logging.warning(f"期望数量: {expected_size}, 实际数量: {len(translated_subtitles)}")
                    continue
                    
                # 验证序号和时间戳是否保持一致
                for (orig_num, orig_ts, _), (trans_num, trans_ts, _) in zip(context_chunk, translated_subtitles):
                    if orig_num != trans_num or orig_ts != trans_ts:
                        logging.warning(f"翻译块 {start_num}-{end_num} 第 {attempt + 1} 次尝试的序号或时间戳不匹配")
                        continue
                    
                # 在其他验证都通过后，进行质量评估
                # 注意：质量评估应该只针对核心内容，不包括上下文
                context_prefix_size = min(current_context_size, chunk_start_idx)
                context_suffix_size = min(current_context_size, len(all_subtitles)-context_end+1)
                core_translated_subtitles = translated_subtitles[context_prefix_size:len(translated_subtitles)-context_suffix_size]
                
                source_content = '\n'.join(text for _, _, text in chunk)
                translated_content = '\n'.join(text for _, _, text in core_translated_subtitles)
                
                # 质量评估时获取修改建议
                quality_score, suggestion = await self.check_translation_quality(source_content, translated_content)
                if quality_score < 5.0:
                    logging.warning(f"翻译块 {start_num}-{end_num} 第 {attempt + 1} 次尝试的质量评分过低: {quality_score}")
                    last_suggestion = suggestion  # 保存这次的修改建议
                    continue
                
                # 在质量评估通过后，处理标点并保存到缓存
                if quality_score >= 5.0:
                    processed_subtitles = self._process_subtitle_blocks(translated_subtitles)
                    
                    # 重新生成处理后的文本
                    processed_text = '\n\n'.join(
                        f'{num}\n{timestamp}\n{text}' 
                        for num, timestamp, text in processed_subtitles
                    )
                    
                    # 保存原始翻译结果到缓存（不保存处理后的结果）
                    if translated_text:
                        self.translation_cache[cache_key] = translated_text
                        self._save_cache()
                    
                    # 从处理后的结果中提取原始块对应的部分
                    result_subtitles = processed_subtitles  # 直接使用处理后的字幕
                    # 根据上下文大小调整切片范围
                    context_prefix_size = min(current_context_size, chunk_start_idx)
                    if len(context_chunk) > len(chunk):
                        result_subtitles = result_subtitles[context_prefix_size:len(result_subtitles)-min(current_context_size, len(all_subtitles)-context_end+1)]
                    
                    result_text = '\n\n'.join(
                        f'{num}\n{timestamp}\n{text}' 
                        for num, timestamp, text in result_subtitles
                    )
                    
                    print(f"完成翻译字幕块 {start_num}-{end_num} (质量评分: {quality_score})")
                    return result_text
                
            except Exception as e:
                logging.error(f"翻译块 {start_num}-{end_num} 出错 (上下文大小: {current_context_size}): {str(e)}")
                continue
                
        logging.error(f"翻译块 {start_num}-{end_num} 失败，已尝试上下文大小范围: {self.context_size}-{self.context_size+max_retries-1}")
        raise Exception(f"翻译块 {start_num}-{end_num} 失败，超过最大重试次数")

    async def translate(self):
        """主翻译流程"""
        content = self.input_file.read_text(encoding='utf-8')
        subtitles = self.parse_subtitle(content)
        total_chunks = len(subtitles) // self.chunk_size + (1 if len(subtitles) % self.chunk_size else 0)
        print(f"总字幕数: {len(subtitles)}")
        print(f"分块大小: {self.chunk_size}")
        print(f"总任务数: {total_chunks}")
        
        # 分块
        chunks = [subtitles[i:i + self.chunk_size] 
                 for i in range(0, len(subtitles), self.chunk_size)]
        
        results = []
        completed = 0
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        async def translate_with_semaphore(chunk, chunk_index):
            nonlocal completed
            async with semaphore:
                # 传入完整的字幕列表，用于获取上下文
                result = await self.translate_chunk(chunk, subtitles)
                completed += 1
                print(f"进度: {completed}/{total_chunks} ({completed/total_chunks*100:.1f}%)")
                return result
        
        tasks = [translate_with_semaphore(chunk, i) for i, chunk in enumerate(chunks)]
        results = await asyncio.gather(*tasks)
        
        print("翻译完成，正在写入文件...")
        final_text = '\n\n'.join(results) + '\n'
        self.output_file.write_text(final_text, encoding='utf-8')
        print(f"已保存到: {self.output_file}")

async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='字幕翻译工具')
    parser.add_argument('input_file', help='输入字幕文件路径')
    parser.add_argument('output_file', help='输出字幕文件路径')
    parser.add_argument('model_type', help='翻译模型')
    parser.add_argument('--chunk-size', type=int, default=30, help='每次翻译的字幕数量(默认: 30)')
    parser.add_argument('--max-concurrent', type=int, default=10, help='最大并发数(默认: 10)')
    parser.add_argument('--context-size', type=int, default=0, help='翻译时包含的上下文字幕数量(默认: 0)')
    parser.add_argument('--split-retry', type=int, default=3, help='每N次重试后拆分任务(默认: 3)')
    parser.add_argument('--keep-punctuation', action='store_true',
                   help='保留字幕末尾的标点符号（默认会去除）')
    args = parser.parse_args()

    translator = SubtitleTranslator(
        input_file=args.input_file,
        output_file=args.output_file,
        model_type=args.model_type,
        chunk_size=args.chunk_size,
        max_concurrent=args.max_concurrent,
        context_size=args.context_size,
        split_retry=args.split_retry,
        keep_punctuation=args.keep_punctuation
    )
    await translator.translate()

if __name__ == "__main__":
    asyncio.run(main())