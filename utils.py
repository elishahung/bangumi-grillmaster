import re


def sanitize_filename(text):
    # 只保留字母、數字、空格、底線與減號

    # 這裡我們採用「只保留安全字元」的邏輯
    safe_name = re.sub(r"[^\w\s-]", "", text).strip()

    # 將多個空格或底線簡化為單一底線
    safe_name = re.sub(r"[-\s]+", "_", safe_name)

    return safe_name
