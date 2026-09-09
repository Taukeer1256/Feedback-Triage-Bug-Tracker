"""
Generates a polished vector visual asset (SVG) of the rendered bug report
for display in the GitHub README.
"""
from pathlib import Path

svg_content = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 920 620" width="100%" height="100%">
  <defs>
    <style>
      .bg { fill: #0d1117; rx: 12px; }
      .header-bar { fill: #161b22; }
      .title { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; font-size: 19px; font-weight: 600; fill: #58a6ff; }
      .text-title { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; font-size: 16px; font-weight: 600; fill: #f0f6fc; }
      .text-body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; font-size: 13px; fill: #c9d1d9; line-height: 1.5; }
      .text-muted { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; font-size: 12px; fill: #8b949e; }
      .badge-med { fill: #d29922; }
      .badge-bg { fill: #21262d; rx: 4px; }
      .card-bg { fill: #161b22; rx: 8px; stroke: #30363d; stroke-width: 1px; }
      .callout { fill: #1f1e14; stroke: #9e6a03; stroke-width: 1px; rx: 6px; }
      .source-tag { font-family: monospace; font-size: 11px; font-weight: bold; fill: #79c0ff; }
      .code-font { font-family: monospace; font-size: 12px; fill: #f0883e; }
    </style>
  </defs>

  <!-- Window Container -->
  <rect width="920" height="620" class="bg" stroke="#30363d" stroke-width="1.5" />

  <!-- Window Titlebar -->
  <path d="M 0 12 Q 0 0 12 0 L 908 0 Q 920 0 920 12 L 920 40 L 0 40 Z" class="header-bar" />
  <circle cx="22" cy="20" r="6" fill="#f85149" />
  <circle cx="42" cy="20" r="6" fill="#e3b341" />
  <circle cx="62" cy="20" r="6" fill="#2ea043" />
  <text x="460" y="25" text-anchor="middle" class="text-muted" font-family="monospace">bug_reports/bug_005_users_receive_triplicate_email_notifications_for_e.md</text>

  <!-- Content Area -->
  <g transform="translate(30, 60)">
    <!-- Document Title -->
    <text x="0" y="24" class="title">Bug Report #5: Users receive triplicate email notifications for every change</text>
    
    <!-- Badges Row -->
    <g transform="translate(0, 38)">
      <rect x="0" y="0" width="82" height="22" class="badge-bg" stroke="#30363d" />
      <text x="41" y="15" text-anchor="middle" class="text-muted" font-size="11" font-weight="600">ISSUE #5</text>

      <rect x="90" y="0" width="105" height="22" rx="4" fill="#3b2300" stroke="#d29922" />
      <text x="142" y="15" text-anchor="middle" fill="#f0883e" font-size="11" font-weight="600">🟡 MEDIUM</text>

      <rect x="203" y="0" width="95" height="22" class="badge-bg" stroke="#30363d" />
      <text x="250" y="15" text-anchor="middle" class="text-muted" font-size="11">RECURRING</text>

      <rect x="306" y="0" width="75" height="22" rx="4" fill="#122c16" stroke="#238636" />
      <text x="343" y="15" text-anchor="middle" fill="#3fb950" font-size="11" font-weight="600">● OPEN</text>

      <rect x="389" y="0" width="130" height="22" class="badge-bg" stroke="#30363d" />
      <text x="454" y="15" text-anchor="middle" class="text-muted" font-size="11">8 reports (4 channels)</text>
    </g>

    <!-- Reproduction Steps Box -->
    <g transform="translate(0, 80)">
      <text x="0" y="16" class="text-title">Reproduction Steps</text>
      
      <rect x="0" y="26" width="860" height="34" class="callout" />
      <text x="14" y="48" fill="#e3b341" font-size="12" font-family="-apple-system, sans-serif">
        ⚠️ Steps marked [INFERRED — needs confirmation] were synthesized by LLM from user tickets.
      </text>

      <rect x="0" y="68" width="860" height="110" class="card-bg" />
      <text x="18" y="93" class="text-body"><tspan fill="#58a6ff" font-weight="600">1.</tspan> Log in to the Flowboard SaaS app using standard credentials.</text>
      <text x="18" y="117" class="text-body"><tspan fill="#58a6ff" font-weight="600">2.</tspan> Navigate to any active project and open a task <tspan class="code-font">[INFERRED — needs confirmation]</tspan>.</text>
      <text x="18" y="141" class="text-body"><tspan fill="#58a6ff" font-weight="600">3.</tspan> Make an edit, status update, or post a comment to the task.</text>
      <text x="18" y="165" class="text-body"><tspan fill="#58a6ff" font-weight="600">4.</tspan> Check the recipient user email inbox — observe <tspan fill="#f85149" font-weight="600">3 identical email notifications</tspan> arrive for the single event.</text>
    </g>

    <!-- Supporting User Evidence -->
    <g transform="translate(0, 280)">
      <text x="0" y="16" class="text-title">Multi-Channel Supporting Evidence</text>
      
      <!-- Card 1: Support Form -->
      <rect x="0" y="28" width="420" height="82" class="card-bg" />
      <text x="14" y="48" class="source-tag">SUPPORT_FORM</text>
      <text x="120" y="48" class="text-muted">· 2026-08-28</text>
      <text x="14" y="68" class="text-body">"Can someone look at the notification system?</text>
      <text x="14" y="86" class="text-body">Getting tripicate [sic] emails for every change."</text>

      <!-- Card 2: Slack -->
      <rect x="440" y="28" width="420" height="82" class="card-bg" />
      <text x="454" y="48" class="source-tag">SLACK</text>
      <text x="505" y="48" class="text-muted">· 2026-08-31</text>
      <text x="454" y="68" class="text-body">"Getting duplicate email notifications —</text>
      <text x="454" y="86" class="text-body">same update, same task, 3 emails in a row."</text>

      <!-- Card 3: Email -->
      <rect x="0" y="122" width="420" height="82" class="card-bg" />
      <text x="14" y="142" class="source-tag">EMAIL</text>
      <text x="65" y="142" class="text-muted">· 2026-09-01</text>
      <text x="14" y="162" class="text-body">"Getting spammed by email — every comment</text>
      <text x="14" y="180" class="text-body">on a task sends me like 4 identical emails."</text>

      <!-- Card 4: WhatsApp -->
      <rect x="440" y="122" width="420" height="82" class="card-bg" />
      <text x="454" y="142" class="source-tag">WHATSAPP</text>
      <text x="535" y="142" class="text-muted">· 2026-09-08</text>
      <text x="454" y="162" class="text-body">"duplicate email notifs are really annoying.</text>
      <text x="454" y="180" class="text-body">same message 2-3x every time"</text>
    </g>

    <!-- Metadata Footer Summary -->
    <g transform="translate(0, 508)">
      <rect x="0" y="0" width="860" height="38" rx="6" fill="#161b22" stroke="#30363d" />
      <text x="20" y="23" class="text-muted">First Seen: <tspan fill="#c9d1d9">2026-08-28</tspan></text>
      <text x="200" y="23" class="text-muted">Last Seen: <tspan fill="#c9d1d9">2026-09-08</tspan></text>
      <text x="375" y="23" class="text-muted">Channels: <tspan fill="#c9d1d9">Email (3), Slack (3), Support (1), WhatsApp (1)</tspan></text>
      <text x="735" y="23" fill="#3fb950" font-weight="600" font-size="12">Flowboard Triage v1.0</text>
    </g>
  </g>
</svg>
'''

assets_dir = Path("assets")
assets_dir.mkdir(exist_ok=True)
svg_path = assets_dir / "bug_report_preview.svg"
svg_path.write_text(svg_content, encoding="utf-8")
print(f"Generated {svg_path}")
