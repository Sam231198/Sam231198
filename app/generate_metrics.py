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


def get_release_downloads(owner: str, repo: str) -> int:
    downloads = 0
    page = 1
    while True:
        url = f"https://api.github.com/repos/{owner}/{repo}/releases"
        params = {"per_page": 100, "page": page}
        releases = github_get(url, params=params)
        if not isinstance(releases, list):
            break
        for release in releases:
            for asset in release.get("assets", []):
                downloads += asset.get("download_count", 0)
        if len(releases) < 100:
            break
        page += 1
    return downloads


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
    sorted_langs = sorted(totals.items(), key=lambda item: item[1], reverse=True)
    return sorted_langs[:5]


def gerar_svg(metrics: dict) -> str:
    width = 800
    height = 380
    padding = 28
    chart_x = 300
    chart_y = 90
    chart_width = 450
    bar_height = 40
    gap = 16

    top_langs = metrics["top_languages"]
    total_bytes = sum(bytes_count for _, bytes_count in top_langs) or 1
    colors = ["#FF7F50", "#1E90FF", "#32CD32", "#FFDC00", "#A020F0"]

    stack_segments = []
    x_offset = chart_x
    for idx, (lang, bytes_count) in enumerate(top_langs):
        width_segment = max(24, int(chart_width * (bytes_count / total_bytes)))
        fill = colors[idx % len(colors)]
        label_color = "#111827" if fill in {"#FFDC00", "#32CD32"} else "#ffffff"

        stack_segments.append(
            f"<rect x='{x_offset}' y='{chart_y}' width='{width_segment}' height='{bar_height}' rx='10' fill='{fill}' />"
            f"<text x='{x_offset + 10}' y='{chart_y + 25}' fill='{label_color}' font-size='14' font-weight='700'>{lang}</text>"
            f"<text x='{x_offset + 10}' y='{chart_y + 42}' fill='{label_color}' font-size='12'>{bytes_count:,} bytes</text>"
        )
        x_offset += width_segment

    top_langs_text = ", ".join(lang for lang, _ in top_langs)
    profile_note = "Perfil não disponível publicamente via API GitHub" if metrics["profile_views"] is None else f'Visitas: {metrics["profile_views"]}'

    return f"""
<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}' viewBox='0 0 {width} {height}'>
  <style>
    .bg {{ fill: #111827; }}
    .title {{ font: bold 26px sans-serif; fill: #f8fafc; }}
    .label {{ font: 16px sans-serif; fill: #d1d5db; }}
    .value {{ font: bold 22px sans-serif; fill: #ffffff; }}
    .small {{ font: 14px sans-serif; fill: #9ca3af; }}
    .card {{ fill: #1f2937; stroke: #374151; stroke-width: 1; rx: 18; }}
  </style>

  <rect width='100%' height='100%' class='bg' rx='24' />
  <text x='{padding}' y='46' class='title'>📊 Métricas GitHub</text>

  <rect x='{padding}' y='70' width='252' height='120' class='card' />
  <text x='{padding + 16}' y='98' class='label'>Commits</text>
  <text x='{padding + 16}' y='128' class='value'>Hoje: {metrics['commits']['hoje']}</text>
  <text x='{padding + 16}' y='156' class='value'>Semana: {metrics['commits']['semana']}</text>
  <text x='{padding + 16}' y='184' class='value'>Mês: {metrics['commits']['mes']}</text>

  <rect x='{padding}' y='208' width='252' height='100' class='card' />
  <text x='{padding + 16}' y='236' class='label'>Projetos criados</text>
  <text x='{padding + 16}' y='274' class='value'>{metrics['repos_count']}</text>
  <text x='{padding + 16}' y='306' class='label'>Downloads de releases</text>
  <text x='{padding + 16}' y='334' class='value'>{metrics['release_downloads']}</text>

  <rect x='{chart_x - 16}' y='{chart_y - 28}' width='{chart_width + 32}' height='{bar_height + 36}' class='card' />
  <text x='{chart_x}' y='{chart_y - 6}' class='label'>Stacks mais usadas (barra empilhada)</text>
  {''.join(stack_segments)}

  <text x='{padding}' y='368' class='small'>{profile_note}</text>
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
        "repos_count": len(repos_criados),
        "release_downloads": sum(
            get_release_downloads(GITHUB_OWNER, repo.get("name"))
            for repo in repos_criados
            if repo.get("name")
        ),
        "profile_views": None,
    }

    svg = gerar_svg(metrics)
    salvar_svg(svg)
    print(json.dumps({
        "repos_count": metrics["repos_count"],
        "top_languages": metrics["top_languages"],
        "commits": metrics["commits"],
        "release_downloads": metrics["release_downloads"],
        "profile_views": "não disponível via API GitHub",
    }, indent=2, ensure_ascii=False))
