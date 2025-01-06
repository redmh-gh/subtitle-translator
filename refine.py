#coding:utf-8
import argparse
from pathlib import Path

class SubtitleBlock:
    def __init__(self, id, start, end, text):
        self.id = id
        self.start = start
        self.end = end
        self.text = text
    def word_count(self):
        return len(self.text.split())
    def split_by_punctuation(self, backward=False):
        # 定义要查找的标点符号列表
        punctuations = [',', '，', '；', ';']
        
        if not backward:
            # 从前向后查找
            for i, char in enumerate(self.text):
                if char in punctuations:
                    return [self.text[:i].strip(), self.text[i+1:].strip()]
        else:
            # 从后向前查找
            for i in range(len(self.text) - 1, -1, -1):
                if self.text[i] in punctuations:
                    return [self.text[:i].strip(), self.text[i+1:].strip()]
        
        return [self.text]
    def parse_ts(self, ts):
        h, m, s = ts.replace(',', '.').split(':')
        return int(float(h) * 3600000 + float(m) * 60000 + float(s) * 1000)
    def is_continuous_with(self, next, tolerance):
        current = self.parse_ts(self.end)
        next = self.parse_ts(next.start)
        # tolerance 100ms
        if abs(current - next) < tolerance:
            return True
        return False

class SubtitleRefiner:
    def __init__(self, min_words, max_length, tolerance):
        self.min_words = min_words
        self.max_length = max_length  
        self.tolerance = tolerance
    def parse_ts_range(self, ts_range):
        start, end = ts_range.split('-->')
        start = start.strip()
        end = end.strip()
        return start, end
    
    def parse_subtitles(self, file_path):
        with open(file_path, 'r', encoding='utf-8') as file:
            lines = file.readlines()
        idx = 0
        blocks = []
        while idx + 3 < len(lines):
            id = lines[idx].strip()
            start, end = self.parse_ts_range(lines[idx+1])
            text = lines[idx+2].strip()
            idx += 3
            while idx < len(lines) and lines[idx].strip() != '':
                text += lines[idx].strip()
                idx += 1
            block = SubtitleBlock(id, start, end, text)
            blocks.append(block)
            idx+=1 # skip empty line

        return blocks
    def refine(self, blocks):
        idx = 0
        nextIdx = 1
        refined_blocks = []
        while nextIdx < len(blocks):
            current = blocks[idx]
            next = blocks[nextIdx]
            if not current.is_continuous_with(next, self.tolerance):
                refined_blocks.append(current)
                idx = nextIdx
                nextIdx = idx + 1
                continue


            # avoid merge too many words
            current_parts = current.split_by_punctuation(backward=True)
            next_parts = next.split_by_punctuation(backward=False)
            if len(current.text) + len(next_parts[0]) > self.max_length and \
                len(next.text) + len(current_parts[len(current_parts)-1]) > self.max_length:

                refined_blocks.append(current)
                idx = nextIdx
                nextIdx = idx + 1
                continue


            tomerge = current_parts[0] if len(current_parts) == 1 else current_parts[1]
            if len(tomerge.split()) <= self.min_words:
                # merge to next subtitle
                #print("merge to next subtitle:", tomerge, "->", next.text)
                next.text = f"{tomerge.strip()} {next.text.strip()}"

                if len(current_parts) > 1:
                    current.text = current_parts[0]
                else:
                    current.text = ''
                    next.start = current.start


            # rerun split by punctuation again, because the text has been changed
            next_parts = next.split_by_punctuation(backward=False)
            tomerge = next_parts[0]
            if len(tomerge.split()) <= self.min_words and current.text != '':
                #print("merge to current subtitle:", current.text, "<-" ,tomerge)
                current.text = f"{current.text.strip()} {tomerge.strip()}"

                if len(next_parts) > 1:
                    next.text = next_parts[1]
                else:
                    next.text = ''
                    current.end = next.end

            # the next is merged, so we should continue to merge current with the next of next
            if next.text == '' and nextIdx + 1 < len(blocks):
                nextIdx += 1
                continue
            
            if current.text != '':
                refined_blocks.append(current)

            idx = nextIdx
            nextIdx = idx + 1
        if idx < len(blocks):
            refined_blocks.append(blocks[idx])
        return refined_blocks
    def format_srt(self, blocks):
        return '\n'.join([f"{idx}\n{block.start} --> {block.end}\n{block.text}\n" for idx, block in enumerate(blocks, 1)])

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('input_file', help='输入字幕文件路径')
    parser.add_argument('output_file', help='输出字幕文件路径')
    parser.add_argument('--min-words', type=int, default=3)
    parser.add_argument('--max-length', type=int, default=42)
    parser.add_argument('--tolerance', type=int, default=100)
    args = parser.parse_args()
    refiner = SubtitleRefiner(min_words=args.min_words, max_length=args.max_length, tolerance=args.tolerance)
    blocks = refiner.parse_subtitles(args.input_file)
    blocks = refiner.refine(blocks)
    out = Path(args.output_file)
    out.write_text(refiner.format_srt(blocks), encoding='utf-8')

if __name__ == "__main__":
    main()
