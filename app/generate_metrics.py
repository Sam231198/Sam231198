import json
import requests

# 1. Busque seus dados (Ex: GitHub API, ou qualquer outra API)
# Aqui simulamos um dado dinâmico, mas poderia ser uma requisição real
commits_hoje = 12 
cafe_consumido = "3 xícaras"

# 2. Monte o layout do seu card usando código SVG puro
svg_content = f"""
<svg xmlns="http://www.w3.org/2000/svg" width="400" height="120" viewBox="0 0 400 120">
  <style>
    .title {{ font: bold 16px sans-serif; fill: #ff2d20; }}
    .text {{ font: 14px sans-serif; fill: #ffffff; }}
    .bg {{ fill: #1a1a1a; rx: 10px; }}
  </style>
  
  <rect width="100%" height="100%" class="bg" />
  
  <text x="20" y="35" class="title">📊 Status do Servidor Interno</text>
  <text x="20" y="70" class="text">💻 Commits enviados hoje: {commits_hoje}</text>
  <text x="20" y="95" class="text">☕ Combustível restante: {cafe_consumido}</text>
</svg>
"""

# 3. Salve o arquivo
with open("my_custom_metric.svg", "w", encoding="utf-8") as f:
    f.write(svg_content)