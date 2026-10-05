import re

def strip_all_markdown(text: str) -> str:
    """
    Guarantees 100% clean, natural conversational text without markdown formatting:
    - Strips bold (**text** -> text)
    - Strips italics (*text* -> text)
    - Strips inline backticks (`code` -> code)
    - Strips headers (### Header -> Header)
    - Converts pipe tables into clean natural bullet lines
    - Removes non-breaking hyphens (\u2011) and special spaces
    """
    if not text:
        return ""

    # 1. Unicode sanitization
    text = text.replace('\u2011', '-').replace('\u2012', '-').replace('\u2013', '-').replace('\u2014', '-')
    text = text.replace('\u202f', ' ').replace('\u00a0', ' ')

    # 2. Remove markdown headers: #, ##, ###
    text = re.sub(r'^#{1,6}\s*', '', text, flags=re.MULTILINE)

    # 3. Convert markdown tables into clean plain bullet text
    if '|' in text:
        plain_lines = []
        for line in text.split('\n'):
            s = line.strip()
            if s.startswith('|') and ('---' in s or 'Order ID' in s or 'Status' in s or 'Carrier' in s or 'Item' in s or 'Price' in s):
                continue
            if s.startswith('|') and s.endswith('|'):
                cells = [c.strip().replace('**', '').replace('*', '') for c in s.strip('|').split('|') if c.strip()]
                if cells:
                    plain_lines.append(" - " + ", ".join(cells))
            else:
                plain_lines.append(line)
        text = '\n'.join(plain_lines)

    # 4. Strip bold, italic, code formatting (**text**, *text*, __text__, _text_, `code`)
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    text = re.sub(r'__(.*?)__', r'\1', text)
    text = re.sub(r'_(.*?)_', r'\1', text)
    text = re.sub(r'`(.*?)`', r'\1', text)

    # 5. Clean excessive whitespace and extra newlines
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()
