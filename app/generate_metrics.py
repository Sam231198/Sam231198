import base64
import json
import os
from datetime import datetime, timezone, timedelta

import requests

GITHUB_OWNER = os.getenv("GITHUB_OWNER", "Sam231198")
GITHUB_REPO = os.getenv("GITHUB_REPO", "Sam231198")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

HEADERS = {
    "Accept": "application/vnd.github.v3+json",
}
if GITHUB_TOKEN:
    HEADERS["Authorization"] = f"token {GITHUB_TOKEN}"

SVG_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "my_custom_metric.svg"))


def github_get(url: str, params: dict | None = None) -> list | dict | None:
    try:
        response = requests.get(url, headers=HEADERS, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException:
        return None


def get_user_repos(owner: str) -> list[dict]:
    repos = []
    page = 1
    while True:
        url = f"https://api.github.com/users/{owner}/repos"
        params = {"per_page": 100, "page": page, "type": "owner", "sort": "updated"}
        page_data = github_get(url, params=params)
        if not page_data:
            break
        repos.extend(page_data)
        if len(page_data) < 100:
            break
        page += 1
    return repos


def get_repo_commit_count(owner: str, repo: str, since: datetime) -> int:
    count = 0
    page = 1
    while True:
        url = f"https://api.github.com/repos/{owner}/{repo}/commits"
        params = {"since": since.isoformat(), "per_page": 100, "page": page}
        commits = github_get(url, params=params)
        if not isinstance(commits, list):
            break
        count += len(commits)
        if len(commits) < 100:
            break
        page += 1
    return count


def get_repo_languages(owner: str, repo: str) -> dict[str, int]:
    url = f"https://api.github.com/repos/{owner}/{repo}/languages"
    data = github_get(url)
    return data if isinstance(data, dict) else {}


FRAMEWORK_SIGNATURES: dict[str, list[tuple[str, str]]] = {
    # manifest_filename -> list of (dependency_substring, framework_display_name)
    "composer.json": [
        ("laravel/framework", "Laravel"),
        ("symfony/", "Symfony"),
        ("cakephp/", "CakePHP"),
        ("codeigniter4/", "CodeIgniter"),
        ("yiisoft/", "Yii"),
    ],
    "package.json": [
        ("next", "Next.js"),
        ("nuxt", "Nuxt"),
        ("@angular/core", "Angular"),
        ("react", "React"),
        ("vue", "Vue"),
        ("svelte", "Svelte"),
        ("@nestjs/core", "NestJS"),
        ("express", "Express"),
        ("astro", "Astro"),
        ("vite", "Vite"),
    ],
    "requirements.txt": [
        ("django", "Django"),
        ("flask", "Flask"),
        ("fastapi", "FastAPI"),
    ],
    "pyproject.toml": [
        ("django", "Django"),
        ("flask", "Flask"),
        ("fastapi", "FastAPI"),
    ],
}


def get_file_content(owner: str, repo: str, path: str) -> str | None:
    url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
    data = github_get(url)
    if not isinstance(data, dict):
        return None
    content_b64 = data.get("content")
    if not content_b64:
        return None
    try:
        return base64.b64decode(content_b64).decode("utf-8", errors="ignore")
    except (ValueError, TypeError):
        return None


def detect_frameworks(repos: list[dict]) -> list[tuple[str, int]]:
    counts: dict[str, int] = {}
    for repo in repos:
        if repo.get("fork"):
            continue
        owner = repo.get("owner", {}).get("login", GITHUB_OWNER)
        repo_name = repo.get("name")
        if not repo_name:
            continue
        found_in_repo: set[str] = set()
        for manifest, signatures in FRAMEWORK_SIGNATURES.items():
            content = get_file_content(owner, repo_name, manifest)
            if not content:
                continue
            lowered = content.lower()
            for dep_key, fw_name in signatures:
                if dep_key in lowered:
                    found_in_repo.add(fw_name)
        for fw_name in found_in_repo:
            counts[fw_name] = counts.get(fw_name, 0) + 1
    return sorted(counts.items(), key=lambda item: item[1], reverse=True)[:6]


def resumo_periodos(owner: str, repo: str) -> dict[str, int]:
    now = datetime.now(timezone.utc)
    hoje = datetime(year=now.year, month=now.month, day=now.day, tzinfo=timezone.utc)
    semana = hoje - timedelta(days=7)
    mes = hoje - timedelta(days=30)

    return {
        "hoje": get_repo_commit_count(owner, repo, hoje),
        "semana": get_repo_commit_count(owner, repo, semana),
        "mes": get_repo_commit_count(owner, repo, mes),
    }


def get_weekly_commits_per_day(owner: str, repo: str) -> list[int]:
    now = datetime.now(timezone.utc)
    today = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    counts = []
    for i in range(6, -1, -1):
        day_start = today - timedelta(days=i)
        day_end = day_start + timedelta(days=1)
        url = f"https://api.github.com/repos/{owner}/{repo}/commits"
        params = {"since": day_start.isoformat(), "until": day_end.isoformat(), "per_page": 100}
        data = github_get(url, params=params)
        counts.append(len(data) if isinstance(data, list) else 0)
    return counts


def top_languages(repos: list[dict]) -> list[tuple[str, int]]:
    totals: dict[str, int] = {}
    for repo in repos:
        if repo.get("fork"):
            continue
        owner = repo.get("owner", {}).get("login", GITHUB_OWNER)
        repo_name = repo.get("name")
        if not repo_name:
            continue
        languages = get_repo_languages(owner, repo_name)
        for lang, bytes_count in languages.items():
            totals[lang] = totals.get(lang, 0) + bytes_count
    # Blade é template do Laravel; Vue é framework
    totals.pop("Blade", None)
    totals.pop("Vue", None)
    # Garantir linguagens solicitadas no SVG
    for lang in ["JavaScript", "Python", "Go"]:
        if lang not in totals:
            totals[lang] = 0
    sorted_langs = sorted(totals.items(), key=lambda item: item[1], reverse=True)
    return sorted_langs[:8]


def gerar_svg(metrics: dict) -> str:
    width = 820
    padding = 24
    card_x = padding
    card_w = width - 2 * padding
    bar_inner_pad = 18
    gap = 12

    top_langs = metrics["top_languages"]
    frameworks = metrics.get("frameworks", [])
    daily_commits = metrics.get("daily_commits", [0] * 7)
    week_commits = metrics["commits"]["semana"]
    total_bytes = sum(b for _, b in top_langs) or 1
    lang_colors = ["#f97316", "#3b82f6", "#22c55e", "#eab308", "#a855f7"]

    # ==============================
    # ROW 1: Commits da Semana
    # ==============================
    commits_card_y = 70
    commits_card_h = 140
    num_area_w = 190
    num_cx = card_x + num_area_w / 2

    spark_x = card_x + num_area_w + 20
    spark_w = card_w - num_area_w - 24
    spark_y = commits_card_y + 22
    spark_h = commits_card_h - 52

    def _sparkline(daily: list[int]) -> str:
        n = len(daily)
        if n < 2:
            return ""
        max_v = max(daily) or 1
        pts = [
            (spark_x + i * spark_w / (n - 1), spark_y + spark_h - (v / max_v) * spark_h * 0.85)
            for i, v in enumerate(daily)
        ]
        fill_path = (
            f"M {pts[0][0]:.1f},{pts[0][1]:.1f} "
            + " ".join(f"L {px:.1f},{py:.1f}" for px, py in pts[1:])
            + f" L {pts[-1][0]:.1f},{spark_y + spark_h:.1f} L {pts[0][0]:.1f},{spark_y + spark_h:.1f} Z"
        )
        line_pts = " ".join(f"{px:.1f},{py:.1f}" for px, py in pts)
        now = datetime.now(timezone.utc)
        labels = ""
        for i in range(n):
            d = now - timedelta(days=n - 1 - i)
            lx = pts[i][0]
            labels += f"<text x='{lx:.1f}' y='{spark_y + spark_h + 14}' fill='#4b5563' font-family='sans-serif' font-size='9' text-anchor='middle'>{d.day:02d}/{d.month:02d}</text>"
        return (
            f"<path d='{fill_path}' fill='#22c55e' fill-opacity='0.15' />"
            f"<polyline points='{line_pts}' fill='none' stroke='#22c55e' stroke-width='2.5' stroke-linejoin='round' stroke-linecap='round' />"
            + labels
        )

    spark_svg = _sparkline(daily_commits)

    # ==============================
    # ROW 2: Linguagens
    # ==============================
    lang_card_y = commits_card_y + commits_card_h + gap
    lang_header_h = 34
    row_h = 32
    lang_card_h = lang_header_h + row_h * max(len(top_langs), 1) + 12
    bar_name_w = 120
    bar_pct_w = 56
    bar_track_x = card_x + bar_inner_pad + bar_name_w
    bar_track_w = card_w - bar_inner_pad - bar_name_w - bar_pct_w - bar_inner_pad
    bar_h = 10

    lang_rows = []
    for idx, (lang, bytes_count) in enumerate(top_langs):
        pct = bytes_count / total_bytes
        row_y = lang_card_y + lang_header_h + idx * row_h
        fill = lang_colors[idx % len(lang_colors)]
        bar_fill_w = max(2, int(bar_track_w * pct))
        ty = row_y + 20
        lang_rows.append(
            f"<text x='{card_x + bar_inner_pad}' y='{ty}' fill='#e5e7eb' font-family='sans-serif' font-size='13' font-weight='600'>{lang}</text>"
            f"<rect x='{bar_track_x}' y='{ty - 8}' width='{bar_track_w}' height='{bar_h}' rx='5' fill='#1e3a4a' />"
            f"<rect x='{bar_track_x}' y='{ty - 8}' width='{bar_fill_w}' height='{bar_h}' rx='5' fill='{fill}' />"
            f"<text x='{bar_track_x + bar_track_w + 10}' y='{ty}' fill='#9ca3af' font-family='sans-serif' font-size='12'>{pct * 100:.1f}%</text>"
        )

    # ==============================
    # ROW 3: Frameworks
    # ==============================
    fw_card_y = lang_card_y + lang_card_h + gap
    fw_card_h = 100
    fw_colors = ["#3b82f6", "#eab308", "#22d3ee", "#ec4899", "#a855f7", "#f97316"]
    fw_area_x = card_x + bar_inner_pad
    fw_area_w = card_w - 2 * bar_inner_pad
    stacked_bar_h = 16
    stacked_bar_y = fw_card_y + 46
    legend_y = fw_card_y + 76

    fw_bars = []
    if frameworks:
        total_fw = sum(count for _, count in frameworks) or 1
        x_cursor = fw_area_x
        for idx, (fw_name, count) in enumerate(frameworks):
            seg_w = max(2, int(fw_area_w * count / total_fw))
            color = fw_colors[idx % len(fw_colors)]
            fw_bars.append(
                f"<rect x='{x_cursor}' y='{stacked_bar_y}' width='{seg_w}' height='{stacked_bar_h}' rx='0' fill='{color}' />"
            )
            leg_x = fw_area_x + idx * (fw_area_w / len(frameworks))
            fw_bars.append(
                f"<rect x='{leg_x}' y='{legend_y}' width='10' height='10' rx='2' fill='{color}' />"
                f"<text x='{leg_x + 14}' y='{legend_y + 9}' fill='#d1d5db' font-family='sans-serif' font-size='11'>{fw_name}</text>"
            )
            x_cursor += seg_w
        fw_bars.insert(0,
            f"<rect x='{fw_area_x}' y='{stacked_bar_y}' width='{fw_area_w}' height='{stacked_bar_h}' rx='8' fill='#1e3a4a' />"
        )
    else:
        fw_bars.append(
            f"<text x='{fw_area_x}' y='{fw_card_y + 60}' fill='#6b7280' font-family='sans-serif' font-size='13'>Nenhum framework detectado.</text>"
        )

    height = fw_card_y + fw_card_h + 40

    return f"""<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}' viewBox='0 0 {width} {height}'>
  <style>
    .title {{ font: bold 22px sans-serif; fill: #f8fafc; }}
    .small {{ font: 12px sans-serif; fill: #9ca3af; }}
    .section {{ font: bold 13px sans-serif; fill: #94a3b8; letter-spacing: 1px; text-transform: uppercase; }}
  </style>

  <rect x='0' y='0' width='{width}' height='{height}' rx='16' fill='#0f172a' />
  <text x='{padding}' y='40' class='title'>Métricas GitHub</text>
  <text x='{padding}' y='58' class='small'>@{GITHUB_OWNER}</text>

  <!-- ROW 1: Commits da Semana -->
  <rect x='{card_x}' y='{commits_card_y}' width='{card_w}' height='{commits_card_h}' rx='12' fill='#1e293b' stroke='#1e3a4a' />
  <text x='{card_x + bar_inner_pad}' y='{commits_card_y + 22}' class='section'>Commits da Semana</text>
  <text x='{num_cx:.1f}' y='{commits_card_y + 88}' fill='#ffffff' font-family='sans-serif' font-size='52' font-weight='700' text-anchor='middle'>{week_commits}</text>
  <text x='{num_cx:.1f}' y='{commits_card_y + 110}' fill='#9ca3af' font-family='sans-serif' font-size='10' letter-spacing='2' text-anchor='middle'>SEMANA</text>
  <line x1='{card_x + num_area_w}' y1='{commits_card_y + 16}' x2='{card_x + num_area_w}' y2='{commits_card_y + commits_card_h - 16}' stroke='#334155' />
  {spark_svg}

  <!-- ROW 2: Linguagens -->
  <rect x='{card_x}' y='{lang_card_y}' width='{card_w}' height='{lang_card_h}' rx='12' fill='#1e293b' stroke='#1e3a4a' />
  <text x='{card_x + bar_inner_pad}' y='{lang_card_y + 22}' class='section'>Linguagens mais usadas</text>
  {''.join(lang_rows)}

  <!-- ROW 3: Frameworks -->
  <rect x='{card_x}' y='{fw_card_y}' width='{card_w}' height='{fw_card_h}' rx='12' fill='#1e293b' stroke='#1e3a4a' />
  <text x='{card_x + bar_inner_pad}' y='{fw_card_y + 24}' class='section'>Frameworks detectados</text>
  {''.join(fw_bars)}

</svg>
"""


def salvar_svg(conteudo: str, path: str = SVG_FILE) -> None:
    with open(path, "w", encoding="utf-8") as arquivo:
        arquivo.write(conteudo)


if __name__ == "__main__":
    repos = get_user_repos(GITHUB_OWNER)
    repos_criados = [repo for repo in repos if not repo.get("fork")]
    metrics = {
        "top_languages": top_languages(repos_criados),
        "commits": resumo_periodos(GITHUB_OWNER, GITHUB_REPO),
        "daily_commits": get_weekly_commits_per_day(GITHUB_OWNER, GITHUB_REPO),
        "repos_count": len(repos_criados),
        "frameworks": detect_frameworks(repos_criados),
    }

    svg = gerar_svg(metrics)
    salvar_svg(svg)
    print(json.dumps({
        "repos_count": metrics["repos_count"],
        "top_languages": metrics["top_languages"],
        "commits": metrics["commits"],
        "frameworks": metrics["frameworks"],
    }, indent=2, ensure_ascii=False))
