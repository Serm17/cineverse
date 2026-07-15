from __future__ import annotations

import html
import pathlib
import re


SOURCE = pathlib.Path("docs/frontend-api-spec-notion.md")
OUTPUT = pathlib.Path("docs/frontend-api-spec-notion.html")


CSS = """
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  line-height: 1.55;
  color: #242424;
  max-width: 980px;
  margin: 40px auto;
  padding: 0 24px;
}
h1 { font-size: 32px; margin: 28px 0 14px; }
h2 {
  font-size: 24px;
  margin: 30px 0 12px;
  border-bottom: 1px solid #e6e6e6;
  padding-bottom: 6px;
}
h3 { font-size: 19px; margin: 24px 0 10px; }
p { margin: 8px 0; }
hr { border: 0; border-top: 1px solid #e6e6e6; margin: 26px 0; }
table {
  border-collapse: collapse;
  width: 100%;
  margin: 10px 0 18px;
  font-size: 14px;
}
th, td {
  border: 1px solid #d8d8d8;
  padding: 8px 10px;
  vertical-align: top;
}
th { background: #f6f6f6; font-weight: 600; }
pre {
  background: #f7f7f7;
  border: 1px solid #e3e3e3;
  border-radius: 6px;
  padding: 12px 14px;
  overflow-x: auto;
  font-size: 13px;
  line-height: 1.45;
}
code {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  background: #f3f3f3;
  padding: 1px 4px;
  border-radius: 4px;
}
pre code { background: transparent; padding: 0; border-radius: 0; }
ul { margin: 8px 0 14px 22px; padding: 0; }
li { margin: 4px 0; }
.copy-note {
  background: #fff8d8;
  border: 1px solid #eedc82;
  padding: 12px 14px;
  border-radius: 8px;
  margin-bottom: 22px;
}
"""


def inline_markdown(value: str) -> str:
    escaped = html.escape(value)
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)


def is_separator_row(value: str) -> bool:
    body = value.replace("|", "").replace("-", "").replace(":", "").strip()
    return body == ""


def render() -> None:
    lines = SOURCE.read_text(encoding="utf-8").splitlines()
    parts: list[str] = [
        "<!doctype html>",
        "<html>",
        "<head>",
        '<meta charset="utf-8">',
        "<title>CineVerse API 명세서</title>",
        f"<style>{CSS}</style>",
        "</head>",
        "<body>",
        (
            '<div class="copy-note"><b>Notion 복붙 방법:</b> '
            "이 HTML 파일을 브라우저로 열고, 화면에 렌더링된 본문을 드래그해서 복사한 뒤 "
            "Notion에 붙여넣으세요. .md 파일 원문을 복사하지 마세요.</div>"
        ),
    ]

    in_code = False
    code_buffer: list[str] = []
    in_list = False
    index = 0

    while index < len(lines):
        line = lines[index]

        if line.startswith("```"):
            if not in_code:
                if in_list:
                    parts.append("</ul>")
                    in_list = False
                in_code = True
                code_buffer = []
            else:
                code = html.escape("\n".join(code_buffer))
                parts.append(f"<pre><code>{code}</code></pre>")
                in_code = False
            index += 1
            continue

        if in_code:
            code_buffer.append(line)
            index += 1
            continue

        if not line.strip():
            if in_list:
                parts.append("</ul>")
                in_list = False
            index += 1
            continue

        if line.strip() == "---":
            if in_list:
                parts.append("</ul>")
                in_list = False
            parts.append("<hr>")
            index += 1
            continue

        if line.startswith("#"):
            if in_list:
                parts.append("</ul>")
                in_list = False
            level = min(len(line) - len(line.lstrip("#")), 3)
            content = line[level:].strip()
            parts.append(f"<h{level}>{inline_markdown(content)}</h{level}>")
            index += 1
            continue

        if (
            line.startswith("|")
            and index + 1 < len(lines)
            and lines[index + 1].startswith("|")
            and is_separator_row(lines[index + 1])
        ):
            if in_list:
                parts.append("</ul>")
                in_list = False
            headers = [cell.strip() for cell in line.strip("|").split("|")]
            parts.append(
                "<table><thead><tr>"
                + "".join(f"<th>{inline_markdown(cell)}</th>" for cell in headers)
                + "</tr></thead><tbody>"
            )
            index += 2
            while index < len(lines) and lines[index].startswith("|"):
                cells = [cell.strip() for cell in lines[index].strip("|").split("|")]
                parts.append(
                    "<tr>"
                    + "".join(f"<td>{inline_markdown(cell)}</td>" for cell in cells)
                    + "</tr>"
                )
                index += 1
            parts.append("</tbody></table>")
            continue

        if line.startswith("- "):
            if not in_list:
                parts.append("<ul>")
                in_list = True
            parts.append(f"<li>{inline_markdown(line[2:].strip())}</li>")
            index += 1
            continue

        if in_list:
            parts.append("</ul>")
            in_list = False
        parts.append(f"<p>{inline_markdown(line.strip())}</p>")
        index += 1

    if in_list:
        parts.append("</ul>")

    parts.extend(["</body>", "</html>"])
    OUTPUT.write_text("\n".join(parts), encoding="utf-8")
    print(OUTPUT)


if __name__ == "__main__":
    render()
