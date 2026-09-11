"""Localization data for /wiki and /api/wiki in English, Vietnamese, and French.

Provides translations for UI chrome, articles, book comparisons, sustainability,
performance documentation, and GodLaws parameter hints.
"""

from __future__ import annotations

SUPPORTED_LANGS = ("en", "vi", "fr")
DEFAULT_LANG = "en"


def normalize_lang(lang: str | None) -> str:
    """Normalize a language code or Accept-Language header to 'en', 'vi', or 'fr'."""
    if not lang:
        return DEFAULT_LANG
    lang = lang.lower().strip()
    if lang.startswith("vi"):
        return "vi"
    if lang.startswith("fr"):
        return "fr"
    if lang.startswith("en"):
        return "en"
    return DEFAULT_LANG


# ---------------------------------------------------------------------
# UI Chrome Translations (header, nav, search, card, badges, footer)
# ---------------------------------------------------------------------
UI_I18N = {
    "en": {
        "title": "Flatland — Living Wiki — World Simulation by Long Phan",
        "description": "Official living wiki and system encyclopedia for Flatland: 2D autonomous World Simulation by Long Phan (long@minhnhan.in).",
        "og_title": "Flatland — Living Wiki | World Simulation by Long Phan",
        "og_desc": "Official living wiki, presets, and mechanics documentation for Flatland World Simulation by Long Phan (long@minhnhan.in).",
        "wiki_heading": "📖 Flatland Wiki & Guide",
        "search_placeholder": "Search laws, routes, docs… ( / )",
        "swagger_docs": "Swagger /docs",
        "openapi": "OpenAPI",
        "guide": "Guide",
        "json_api": "JSON",
        "live_world": "← Demo",
        "presets_label": "Presets:",
        "dev_by": "Developed by",
        "dev_name": "Long Phan",
        "built_with": "Built with OpenCode & Antigravity<br/>Inspired by Edwin A. Abbott",
        "badge_laws": "{laws} laws",
        "badge_routes": "{routes} routes",
        "badge_presets": "{presets} presets",
        "sphere_motto": "The Sphere sets laws, never a life",
        "landing_page": "Landing Page",
        "footer": "Generated from live code — <code>Config</code> defaults + <code>GodLaws</code> + <code>app.routes</code>. Official living documentation & encyclopedia for Flatland. · Developed by <strong>Long Phan</strong> — <a href=\"mailto:long@minhnhan.in\">long@minhnhan.in</a> · Demo: <a href=\"https://world.minhnhan.in\">world.minhnhan.in</a> · Landing: <a href=\"https://longphanmn.github.io/flatland/\" target=\"_blank\" rel=\"noopener noreferrer\">longphanmn.github.io/flatland</a> · <a href=\"https://github.com/longphanmn/flatland\" target=\"_blank\" rel=\"noopener noreferrer\">GitHub</a> · Built with OpenCode & Antigravity",
        "preset_col_name": "Preset",
        "preset_col_laws": "Key laws",
        "preset_col_apply": "Apply",
        "preset_via_app": "Via the app UI or TUI",
        "preset_sidebar_note": "Read-only here — apply presets in the app UI or TUI.",
        "active_badge": "ACTIVE",
        "api_ref_title": "# API reference\n\nLive routes from `app.routes` + Swagger at [/docs](/docs). Try `curl` examples below.",
        "laws_title": "# Laws of the Sphere\n\nEvery law in `GodLaws` (`protocol.py:108`) with type/range/default. Set via `POST /api/laws` or presets.",
        "presets_title": "# Presets — one-click worlds\n\nSustainable is the 1000-day gentle world. Apply via The Sphere panel or `POST /api/presets/{name}?reset`.",
        "roadmap_title": "Roadmap",
        "roadmap_desc": "# Roadmap\n\nSee `TODO.md` (active) + `docs/roadmap-archive.md` (completed) — {sections} sections + {laws} laws + {routes} routes + {presets} presets. Wiki extends Guide with presets, sustainability & playground.",
        "law_col_law": "Law",
        "law_col_type": "Type",
        "law_col_range": "Range",
        "law_col_default": "Default",
        "law_col_hint": "Hint + docs",
        "route_col_method": "Method",
        "route_col_path": "Path",
        "route_col_name": "Name",
        "route_col_desc": "Description",
        "curl_title": "## Curl playground",
        "nav_group_core": "Core Knowledge",
        "nav_group_systems": "Systems & Balance",
        "nav_group_reference": "Rules & Reference",
        "live_pulse": "Demo",
    },
    "vi": {
        "title": "Flatland — Bách khoa toàn thư & Wiki — Mô phỏng Thế giới bởi Long Phan",
        "description": "Tài liệu bách khoa toàn thư và wiki sống chính thức của Flatland: Mô phỏng thế giới 2D tự hành phát triển bởi Long Phan (long@minhnhan.in).",
        "og_title": "Flatland — Living Wiki | Hệ thống Mô phỏng Thế giới bởi Long Phan",
        "og_desc": "Tài liệu chính thức về cơ chế mô phỏng, thiết lập mẫu và thiên luật tự nhiên của Flatland bởi Long Phan (long@minhnhan.in).",
        "wiki_heading": "📖 Bách khoa toàn thư Flatland",
        "search_placeholder": "Tìm kiếm thiên luật, endpoint, tài liệu… ( / )",
        "swagger_docs": "Tài liệu Swagger /docs",
        "openapi": "OpenAPI",
        "guide": "Cẩm nang",
        "json_api": "Dữ liệu JSON",
        "live_world": "← Bản demo",
        "presets_label": "Thiết lập mẫu:",
        "dev_by": "Phát triển bởi",
        "dev_name": "Long Phan",
        "built_with": "Xây dựng với OpenCode & Antigravity<br/>Lấy cảm hứng từ Edwin A. Abbott",
        "badge_laws": "{laws} thiên luật",
        "badge_routes": "{routes} endpoint",
        "badge_presets": "{presets} mẫu",
        "sphere_motto": "Khối Cầu định đoạt thiên luật, không can thiệp số mệnh",
        "landing_page": "Trang chủ",
        "footer": "Trích xuất trực tiếp từ mã nguồn — <code>Config</code> + <code>GodLaws</code> + <code>app.routes</code>. Bách khoa toàn thư sống chính thức của Flatland. · Phát triển bởi <strong>Long Phan</strong> — <a href=\"mailto:long@minhnhan.in\">long@minhnhan.in</a> · Bản demo: <a href=\"https://world.minhnhan.in\">world.minhnhan.in</a> · Trang chủ: <a href=\"https://longphanmn.github.io/flatland/\" target=\"_blank\" rel=\"noopener noreferrer\">longphanmn.github.io/flatland</a> · <a href=\"https://github.com/longphanmn/flatland\" target=\"_blank\" rel=\"noopener noreferrer\">GitHub</a> · Xây dựng với OpenCode & Antigravity",
        "preset_col_name": "Thiết lập mẫu",
        "preset_col_laws": "Quy luật trọng tâm",
        "preset_col_apply": "Áp dụng",
        "preset_via_app": "Thực hiện qua ứng dụng hoặc TUI",
        "preset_sidebar_note": "Chỉ xem tại đây — áp dụng mẫu thông qua giao diện ứng dụng hoặc TUI.",
        "active_badge": "ĐANG DÙNG",
        "api_ref_title": "# Tham chiếu API\n\nDanh sách endpoint từ `app.routes` + tài liệu tương tác tại [/docs](/docs). Xem các ví dụ `curl` bên dưới.",
        "laws_title": "# Thiên luật của Khối Cầu (The Sphere)\n\nToàn bộ định luật trong `GodLaws` (`protocol.py:108`) kèm kiểu dữ liệu, phạm vi và giá trị mặc định. Thay đổi qua `POST /api/laws` hoặc chọn thiết lập mẫu.",
        "presets_title": "# Thiết lập mẫu — Định hình thế giới với 1 chạm\n\n'sustainable' mang lại nền thái bình thịnh trị 1000 ngày. Áp dụng qua bảng Khối Cầu hoặc lệnh `POST /api/presets/{name}?reset`.",
        "roadmap_title": "Lộ trình phát triển",
        "roadmap_desc": "# Lộ trình phát triển\n\nXem `TODO.md` (đang mở) + `docs/roadmap-archive.md` (đã hoàn thành) — {sections} phần + {laws} thiên luật + {routes} endpoint + {presets} thiết lập mẫu. Wiki bổ trợ Cẩm nang với các preset, cân bằng sinh thái và công cụ thử nghiệm.",
        "law_col_law": "Thiên luật",
        "law_col_type": "Kiểu",
        "law_col_range": "Khoảng",
        "law_col_default": "Mặc định",
        "law_col_hint": "Giải thích & tài liệu",
        "route_col_method": "Phương thức",
        "route_col_path": "Đường dẫn",
        "route_col_name": "Tên hàm",
        "route_col_desc": "Mô tả",
        "curl_title": "## Khu vực chạy thử Curl",
        "nav_group_core": "Tri thức Cốt lõi",
        "nav_group_systems": "Hệ thống & Cân bằng",
        "nav_group_reference": "Thiên luật & Tham chiếu",
        "live_pulse": "Bản demo",
    },
    "fr": {
        "title": "Flatland — Wiki Vivant & Encyclopédie — Simulation de Monde par Long Phan",
        "description": "Wiki vivant officiel et encyclopédie du système pour Flatland : simulation 2D autonome de vie artificielle par Long Phan (long@minhnhan.in).",
        "og_title": "Flatland — Wiki Vivant | Simulation de Monde par Long Phan",
        "og_desc": "Documentation officielle vivante, préréglages et mécanique du monde de Flatland par Long Phan (long@minhnhan.in).",
        "wiki_heading": "📖 Encyclopédie Flatland",
        "search_placeholder": "Rechercher lois, routes, docs… ( / )",
        "swagger_docs": "Swagger /docs",
        "openapi": "OpenAPI",
        "guide": "Guide",
        "json_api": "JSON",
        "live_world": "← Démo",
        "presets_label": "Préréglages :",
        "dev_by": "Développé par",
        "dev_name": "Long Phan",
        "built_with": "Conçu avec OpenCode & Antigravity<br/>Inspiré par Edwin A. Abbott",
        "badge_laws": "{laws} lois",
        "badge_routes": "{routes} routes API",
        "badge_presets": "{presets} préréglages",
        "sphere_motto": "La Sphère dicte les lois, jamais une vie",
        "landing_page": "Page d'accueil",
        "footer": "Généré à partir du code source en temps réel — Valeurs <code>Config</code> + <code>GodLaws</code> + <code>app.routes</code>. Documentation vivante officielle et encyclopédie de Flatland. · Développé par <strong>Long Phan</strong> — <a href=\"mailto:long@minhnhan.in\">long@minhnhan.in</a> · Démo : <a href=\"https://world.minhnhan.in\">world.minhnhan.in</a> · Accueil : <a href=\"https://longphanmn.github.io/flatland/\" target=\"_blank\" rel=\"noopener noreferrer\">longphanmn.github.io/flatland</a> · <a href=\"https://github.com/longphanmn/flatland\" target=\"_blank\" rel=\"noopener noreferrer\">GitHub</a> · Conçu avec OpenCode & Antigravity",
        "preset_col_name": "Préréglage",
        "preset_col_laws": "Lois fondamentales",
        "preset_col_apply": "Appliquer",
        "preset_via_app": "Via l'app ou le TUI",
        "preset_sidebar_note": "Lecture seule ici — appliquez via l'app ou le TUI.",
        "active_badge": "ACTIF",
        "api_ref_title": "# Référence de l'API\n\nRoutes en direct issues de `app.routes` + documentation Swagger à [/docs](/docs). Essayez les exemples `curl` ci-dessous.",
        "laws_title": "# Lois de la Sphère (The Sphere)\n\nTous les champs de `GodLaws` (`protocol.py:108`) — type, plage et valeur par défaut. Modifiables via `POST /api/laws` ou par préréglage.",
        "presets_title": "# Préréglages — Mondes prêts en un clic\n\n'sustainable' offre une paix durable de 1000 jours. Appliquez via le panneau La Sphère ou `POST /api/presets/{name}?reset`.",
        "roadmap_title": "Feuille de route",
        "roadmap_desc": "# Feuille de route\n\nVoir `TODO.md` (actif) + `docs/roadmap-archive.md` (terminé) — {sections} sections + {laws} lois + {routes} routes + {presets} préréglages. Le Wiki enrichit le Guide avec les préréglages, la durabilité & les tests.",
        "law_col_law": "Loi",
        "law_col_type": "Type",
        "law_col_range": "Plage",
        "law_col_default": "Défaut",
        "law_col_hint": "Indice & docs",
        "route_col_method": "Méthode",
        "route_col_path": "Chemin",
        "route_col_name": "Nom",
        "route_col_desc": "Description",
        "curl_title": "## Exemples de requêtes Curl",
        "nav_group_core": "Connaissances de Base",
        "nav_group_systems": "Systèmes & Équilibre",
        "nav_group_reference": "Lois & Référence",
        "live_pulse": "Démo",
    },
}


# ---------------------------------------------------------------------
# Navigation Section Slugs and Titles with Categories and Icons
# ---------------------------------------------------------------------
NAV_SECTIONS = [
    # Core Knowledge
    ("overview", {"en": "Overview", "vi": "Tổng quan", "fr": "Aperçu"}, "core", "📖"),
    ("book-comparison", {"en": "Flatland Book vs Simulation", "vi": "Tiểu thuyết Abbott vs Mô phỏng", "fr": "Livre Flatland vs Simulation"}, "core", "📐"),
    ("quickstart", {"en": "Quickstart", "vi": "Bắt đầu nhanh", "fr": "Démarrage rapide"}, "core", "⚡"),
    ("how-the-world-works", {"en": "How the world works", "vi": "Nguyên lý vận hành", "fr": "Fonctionnement du monde"}, "core", "⚙️"),

    # Systems & Balance
    ("sustainability", {"en": "Sustainability", "vi": "Tính bền vững & Cân bằng", "fr": "Durabilité & Équilibre"}, "systems", "🌿"),
    ("performance", {"en": "Performance & Scale", "vi": "Hiệu năng & Quy mô", "fr": "Performance & Échelle"}, "systems", "🚀"),
    ("codebase-map", {"en": "Codebase map", "vi": "Kiến trúc mã nguồn", "fr": "Carte du code source"}, "systems", "🗺️"),
    ("data-model-protocol", {"en": "Data model & protocol", "vi": "Mô hình dữ liệu & Giao thức", "fr": "Modèle de données & Protocole"}, "systems", "💾"),

    # Laws & Reference
    ("god-laws", {"en": "Laws of the Sphere", "vi": "Thiên luật Khối Cầu", "fr": "Lois de la Sphère"}, "reference", "⚖️"),
    ("presets", {"en": "Presets", "vi": "Thiết lập mẫu", "fr": "Préréglages"}, "reference", "🎯"),
    ("api-reference", {"en": "API reference", "vi": "Tham chiếu API", "fr": "Référence de l'API"}, "reference", "🔌"),
    ("configuration-ops", {"en": "Configuration & ops", "vi": "Cấu hình & Vận hành", "fr": "Configuration & Exploitation"}, "reference", "🛠️"),
]


# ---------------------------------------------------------------------
# Articles Markdown Content
# ---------------------------------------------------------------------
WIKI_OVERVIEW_MD_I18N = {
    "en": r"""
# Flatland Wiki & Encyclopedia

> **Landing Page**: [https://longphanmn.github.io/flatland/](https://longphanmn.github.io/flatland/)  
> **Source Code**: [https://github.com/longphanmn/flatland](https://github.com/longphanmn/flatland)  
> **Developed by [Long Phan](mailto:long@minhnhan.in)** ([long@minhnhan.in](mailto:long@minhnhan.in) · Demo: [world.minhnhan.in](https://world.minhnhan.in))  
> Built and refined using **OpenCode** and **Antigravity** · Developed from the core ideas of **Edwin A. Abbott's *Flatland: A Romance of Many Dimensions*** (1884).

Flatland is an autonomous 2D artificial life and world simulation developed from the foundational mathematical and spatial ideas of Edwin A. Abbott's 1884 classic *Flatland*. 

### Design Philosophy
This project is **developed from the Flatland idea rather than mimicking the book literally**. It adopts Abbott's core premises — 2D planar constraints, geometric vertex hierarchies, atmospheric perception, and higher-dimensional observation — as a foundation to create a **living, evolutionary artificial life ecosystem that organically changes and expands over time**.

### Core Architecture & Systems
- **The Sphere (God Model)**: The Sphere (God) sets global **laws of nature** (carrying capacity, food growth, metabolism, disease, climate) from Spaceland, never intervening in individual lives. Configured via a dedicated **🎯 Presets** selector and 6 streamlined **⚖️ Macro Domains** with live search and dual sliders. Organisms navigate continuously via 16-sensor raycasts and Micro-RNN neural actuators.
- **Botanical Ecology & Functional Nutrition**: 6 diverse plant species (`grass`, `grain`, `berry`, `medicinal_herb`, `mushroom`, `poisonous`) with distinct caloric densities, decay clocks, infection remedy effects, and targeted health-based foraging preferences.
- **Cognitive Agency & Clan Social Intelligence**: Multi-objective utility AI replaces rigid if/else trees (evaluating survival, duty, traits, and kin needs); spatial waypoint mental maps; tactical soldier phalanxes, line kiting maneuvers, interpersonal trust-based buddy pairing, autonomous clan task boards (dynamic labor division), governance archetypes (Monarchy, Theocracy, Junta, Republic), adaptive bylaws (winter rationing, martial law), calculated Casus Belli, inter-clan trade caravans, and annual autumn harvest festivals.
- **Autonomous Evolution & Culture**: 6 heritable personality archetypes (`brave`, `cautious`, `altruistic`, `greedy`, `explorer`, `builder`), craftable tools (spears, baskets, herb poultices, chieftain crowns), 4 mastery skills (Farming 🌾, Combat ⚔️, Foraging 🦴, Healing 🌿), earned dynamic titles, oral lore passed from elders to youth in houses, and live thought bubbles.
- **Realistic Energy & Metabolism**: Infant low metabolism ($0.45\times$ energy decay), combat stamina expenditure, and autonomous field food reserve management via baskets.
- **Settlements & Diplomacy**: Walled houses with creature-sized doors, multi-house clan territories, settlement food larders, mutual coalitions, tributary pacts, and schisms.
- **Geometric Physics & Morphological Evolution (K∈[3,24])**: Polar genomes $(r_i,\phi_i)$ $K\in[3,24]$ (`KMAX 24`, `morphology_engine.py`) with SoA `physical_traits` trait baking ($A,P,I_{zz},\theta_{\min},asym,D_{mult}$) and SAT narrowphase (broadphase $r_{\max}$ + circle fallback $K\ge24$ & $asym<0.05$ + edge normals); annealing $\lambda(g)$ blends Abbott templates → free evolution, energetic asymmetry, neural courtship, and extinction safeguards ($\eta(N)$, Tier1/2/3 genesis, mercy).
- **Evolutionary Genome Mirror** <span id="genome-mirror"></span>: Dynamic visual phenotype rendering where each creature's body, corolla aura, and chromatic luminescence directly mirror its living genome, generational depth (Gen 0 → 2000+), and physical mutations across millennia.
- **Real-Time Synchronization**: Deterministic fixed-rate engine loop streaming state over WebSocket (`/ws`) at ~30–60 FPS with durable SQLite historical chronicle storage.
""",
    "vi": r"""
# Bách khoa toàn thư & Wiki Flatland

> **Trang chủ / Landing Page**: [https://longphanmn.github.io/flatland/](https://longphanmn.github.io/flatland/)  
> **Mã nguồn**: [https://github.com/longphanmn/flatland](https://github.com/longphanmn/flatland)  
> **Phát triển bởi [Long Phan](mailto:long@minhnhan.in)** ([long@minhnhan.in](mailto:long@minhnhan.in) · Bản demo: [world.minhnhan.in](https://world.minhnhan.in))  
> Xây dựng và hoàn thiện bằng **OpenCode** & **Antigravity** · Phát triển từ ý niệm nền tảng trong danh tác ***Flatland: A Romance of Many Dimensions*** (1884) của **Edwin A. Abbott**.

Flatland là một thế giới mô phỏng sự sống nhân tạo 2D tự hành, vận dụng sáng tạo các tiền đề toán học và không gian từ tác phẩm kinh điển *Flatland* (Xứ Phẳng) xuất bản năm 1884 của Edwin A. Abbott.

### Triết lý thiết kế
Dự án được **phát triển từ ý niệm cốt lõi của Xứ Phẳng chứ không sao chép máy móc từng câu chữ trong tiểu thuyết**. Hệ thống tiếp thu các tiên đề hình học của Abbott — mặt phẳng 2D, trật tự xã hội dựa trên số đỉnh, tầm nhìn trong sương mù và góc quan sát từ chiều không gian cao hơn — để kiến tạo một **hệ sinh thái sự sống nhân tạo tự sinh, tự thích nghi và phát triển hữu cơ theo thời gian**.

### Kiến trúc & Các hệ thống cốt lõi
- **Khối Cầu (Đấng Sáng Tạo)**: Khối Cầu (The Sphere) ban hành **thiên luật tự nhiên** (sức tải môi trường, tốc độ mọc cây, trao đổi chất, dịch bệnh, thời tiết) từ Spaceland, hoàn toàn không can thiệp thô bạo vào số mệnh cá thể. Người dùng có thể điều chỉnh qua **🎯 Thiết lập mẫu** và 6 **⚖️ Lĩnh vực Vĩ mô** bằng thanh trượt trực quan. Sinh vật định hướng liên tục qua 16 cảm biến tia quét và mạng nơ-ron Micro-RNN.
- **Sinh thái thực vật & Dinh dưỡng chức năng**: 6 loài thực vật chuyên biệt (`cỏ`, `lúa mì`, `quả mọng`, `thảo dược`, `nấm`, `cây độc`) với mật độ calo riêng biệt, đồng hồ phân hủy, dược tính trị bệnh và hành vi tự tìm kiếm thức ăn theo nhu cầu sinh tồn.
- **Trí tuệ nhân tạo & Xã hội thị tộc**: AI thỏa dụng đa mục tiêu đánh giá sinh tồn, nghĩa vụ và gắn kết huyết thống; bản đồ tinh thần ghi nhớ địa hình; đội hình phalanx của binh sĩ, chiến thuật thả diều linh hoạt của nữ giới (đoạn thẳng), kết bạn đồng hành dựa trên tin cậy, phân công lao động thị tộc, các thể chế (Quân chủ, Thần quyền, Quân phiệt, Cộng hòa), sắc lệnh thích ứng (phát chẩn mùa đông, thiết quân luật), cớ tuyên chiến (Casus Belli), đoàn buôn liên tộc và đại yến mùa thu mừng vụ mùa.
- **Tiến hóa tự hành & Bản sắc văn hóa**: 6 hình mẫu tính cách di truyền (`dũng cảm`, `thận trọng`, `vị tha`, `tư lợi`, `khai phá`, `xây dựng`), công cụ chế tác (giáo, túi cói, thuốc đắp, vương miện thủ lĩnh), 4 kỹ năng tinh thông (Nông canh 🌾, Chiến đấu ⚔️, Hái lượm 🦴, Y thuật 🌿), tước hiệu động, truyền dạy tri thức trong nhà ở và hiển thị suy nghĩ trực quan.
- **Năng lượng & Trao đổi chất thực tế**: Con non tiêu hao ít năng lượng ($0.45\times$), thể lực sụt giảm khi tác chiến, và thói quen dự trữ thức ăn trong túi cói.
- **Ấp định cư & Bang giao**: Nhà tường kín có cửa ra vào vừa vặn kích thước cơ thể, lãnh thổ thị tộc đa công trình, kho lương chung, khối liên minh phòng thủ, nộp cống và phân liệt ly khai khi bất mãn.
- **Vật lý hình học & Đột biến hình thái (K∈[3,24])**: Bộ gen cực $(r_i,\phi_i)$ $K\in[3,24]$ (`KMAX 24`, `morphology_engine.py`) với đặc tính thể chất tích hợp ($A,P,I_{zz},\theta_{\min},asym,D_{mult}$) và va chạm đa giác SAT; cơ chế ủ nhiệt $\lambda(g)$ dung hòa giữa chuẩn mực Abbott cổ điển và tiến hóa tự do, ghép đôi nơ-ron, cùng mạng lưới bảo hộ chống tuyệt diệt ($\eta(N)$, Phép Miracle Khai Thế Cấp 1/2/3).
- **Gương Phản chiếu Bộ gen Tiến hóa** <span id="genome-mirror"></span>: Trực quan hóa kiểu hình sinh động nơi thân thể, vành nhật hoa và ánh sáng phát quang phản chiếu trực tiếp bộ gen sống, độ sâu thế hệ (Gen 0 → 2000+) và đột biến thể chất qua hàng thiên niên kỷ.
- **Đồng bộ hóa thời gian thực**: Vòng lặp mô phỏng xác định truyền phát trạng thái thế giới qua WebSocket (`/ws`) ở tốc độ ~30–60 FPS kết hợp lưu trữ biên niên sử bền vững trên SQLite.
""",
    "fr": r"""
# Encyclopédie & Wiki Flatland

> **Page d'accueil / Landing Page** : [https://longphanmn.github.io/flatland/](https://longphanmn.github.io/flatland/)  
> **Code Source**: [https://github.com/longphanmn/flatland](https://github.com/longphanmn/flatland)  
> **Développé par [Long Phan](mailto:long@minhnhan.in)** ([long@minhnhan.in](mailto:long@minhnhan.in) · Démo : [world.minhnhan.in](https://world.minhnhan.in))  
> Conçu et perfectionné avec **OpenCode** & **Antigravity** · Développé à partir des concepts fondamentaux de l'œuvre classique d'**Edwin A. Abbott, *Flatland: A Romance of Many Dimensions*** (1884).

Flatland est une simulation autonome de vie artificielle et d'écosystème en 2D, conçue d'après les idées mathématiques et spatiales d'Edwin A. Abbott.

### Philosophie de conception
Ce projet est **développé à partir de l'idée de Flatland plutôt que d'imiter servilement le livre**. Il adopte les postulats d'Abbott — contraintes du plan 2D, hiérarchie géométrique selon le nombre de sommets, perception atmosphérique et regard depuis une dimension supérieure — pour fonder un **écosystème de vie artificielle évolutif et organique qui se métamorphose au fil du temps**.

### Architecture et systèmes fondamentaux
- **La Sphère (Modèle divin)** : La Sphère établit les **lois universelles de la nature** (capacité de charge, croissance végétale, métabolisme, maladies, climat) depuis Spaceland (l'espace tridimensionnel), sans jamais intervenir arbitrairement dans les existences individuelles. Paramétrable via un sélecteur de **🎯 Préréglages** et 6 **⚖️ Domaines Macro** avec recherche en temps réel et doubles curseurs. Les organismes se repèrent grâce à 16 capteurs de rayons et des actionneurs neuronaux Micro-RNN.
- **Écologie botanique & Nutrition fonctionnelle** : 6 espèces végétales distinctes (`herbe`, `grain`, `baie`, `herbe_médicinale`, `champignon`, `toxique`) dotées de densités caloriques propres, de cycles de flétrissement, d'effets curatifs et d'orientations alimentaires selon l'état de santé.
- **Agence cognitive & Intelligence sociale des clans** : Une IA d'utilité multi-objectifs remplace les arbres conditionnels rigides ; cartographie mentale par jalons spatiaux ; phalanges tactiques de soldats, manœuvres d'évitement des femmes-lignes, formation de binômes de confiance, tableaux de tâches claniques autonomes, régimes politiques variés (Monarchie, Théocratie, Junte, République), décrets d'urgence (rationnement hivernal, loi martiale), caravanes de commerce et fêtes automnales des moissons.
- **Évolution autonome & Culture** : 6 archétypes de personnalité héréditaires (`brave`, `prudent`, `altruiste`, `avare`, `explorateur`, `bâtisseur`), fabrication d'outils (lances, paniers, cataplasmes, couronnes), 4 compétences d'élite (Agriculture 🌾, Combat ⚔️, Cueillette 🦴, Soins 🌿), titres honorifiques dynamiques, transmission orale des aînés aux jeunes dans les demeures et bulles de pensées en direct.
- **Métabolisme & Dynamique énergétique réalistes** : Faible dépense chez les nouveau-nés ($0.45\times$), coût d'endurance au combat et gestion de réserves portatives via des paniers.
- **Colonies & Diplomatie** : Bâtisses closes avec portes ajustées, territoires multi-maisons, greniers communautaires, coalitions de défense mutuelle, tributs et scissions claniques.
- **Physique géométrique & Évolution morphologique (K∈[3,24])** : Génomes polaires $(r_i,\phi_i)$ $K\in[3,24]$ (`KMAX 24`, `morphology_engine.py`) avec calcul des propriétés physiques SoA ($A,P,I_{zz},\theta_{\min},asym,D_{mult}$) et détection fine SAT ; le recuit morphologique $\lambda(g)$ assure la transition des gabarits d'Abbott vers une spéciation libre, parade nuptiale neuronale et sauvegardes contre l'extinction ($\eta(N)$, miracles de la Genèse).
- **Miroir Génomique Évolutif** <span id="genome-mirror"></span> : Rendu visuel phénotypique dynamique où le corps, la corolle et la luminescence de chaque créature reflètent son génome vivant, sa profondeur générationnelle (Gén 0 → 2000+) et ses mutations physiques à travers les millénaires.
- **Synchronisation en temps réel** : Moteur déterministe diffusant l'état du monde via WebSocket (`/ws`) à ~30–60 FPS avec persistance historique sur SQLite.
""",
}

SUSTAINABILITY_MD_I18N = {
    "en": r"""
# Sustainability — Multi-Generational Balance

The world self-balances across hundreds of days and multi-generational dynastic flourishing under tuned ecological and social equilibrium.

## Curated Presets

- **balance** ⚖️ (Default) — Goldilocks harmony tuned for **200–350 inhabitants** with 380 food, carrying capacity 400 (max 500), gentle wars, rare predation, agriculture, density damping ($\xi$), extinction safeguards ($\eta$), and flourishing multi-generational clans.
- **sustainable** 🌿 — 1000-day prosperous peace: abundant food (550), carrying capacity 550 (max 600), rich granaries, harvest festivals, banquets, and gentle damping.
- **theocracy** 🔮 — Age of the Sphere: sacred avatars, glowing temples, avatar miracles, 3D epiphanies, holy synods, and divine tithes.
- **warlords** ⚔️ — Clash of clans: imperial conquests, granary raids, house takeovers, territorial expansion, and defensive coalitions.
- **chaos** 🔥 — High predator ratio, lethal wars, wildfires, earthquakes, frequent plagues, and fast seasonal turnover.
- **extinction** 💀 — Severe famine (120 food), harsh winter (0.30×), high exposure decay, testing societal resilience under collapse.
- **boom** 🚀 — High reproduction, 440 food, carrying capacity 800 (max 850) for monumental metropolis testing.

Use: `curl -X POST localhost:8000/api/presets/balance?reset=true` or use The Sphere (God Panel) preset selector.

## Dynamic Homeostasis & Extinction Prevention

Flatland includes two complementary closed-loop homeostatic feedback engines:

### 1. Density-Dependent Soft-Cap Damping ($\xi$)
When population $N$ exceeds carrying capacity $K_{cap}$, the overshoot ratio $\xi = (N - K_{cap}) / K_{cap}$ acts as a non-linear brake:
- **Birth Suppression**: $R_{birth} = R_0 / (1 + \text{damping\_steepness} \cdot \xi^2)$
- **Crowding Metabolic Stress**: $M_{decay} = M_0 \cdot (1 + \text{crowding\_stress\_mult} \cdot \xi)$
- **Resource Strain**: Plant growth and spread slow down proportionally to ecosystem saturation.

### 2. Extinction Safeguards & Genesis Miracles ($\eta$)
When population drops below $K_{safe} = K_{cap} \times \text{safeguard\_relief\_ratio}$, emergency relief kicks in:
- **Tier 1 ($\eta \le 0.5$)**: Famine relief, metabolic energy discount up to 40%, plant growth acceleration up to 60%.
- **Tier 2 ($\eta > 0.5$)**: Critical relief, reproduction cooldown halved, infant euthanasia suspended (`safeguard_morph_mercy`).
- **Tier 3 ($N \le K_{crit}$)**: The Sphere intervenes with a Genesis Miracle, creating `safeguard_genesis_batch` pristine regular beings to ensure species survival.
""",
    "vi": r"""
# Tính bền vững — Cân bằng sinh thái Đa thế hệ

Thế giới tự động duy trì sự cân bằng qua hàng trăm ngày và tạo điều kiện cho các thị tộc hưng thịnh truyền đời dưới trạng thái cân bằng sinh thái và xã hội hoàn chỉnh.

## Các thiết lập mẫu tuyển chọn (Presets)

- **balance** ⚖️ (Mặc định) — Trạng thái cân bằng vàng cho **200–350 cư dân** với 380 thức ăn, sức tải 400 (tối đa 500), chiến tranh vừa độ, chuỗi săn mồi cân bằng, nông nghiệp bài bản, tự hãm mật độ ($\xi$), cơ chế bảo hộ tuyệt chủng ($\eta$) và các thị tộc đa thế hệ phát triển phồn vinh.
- **sustainable** 🌿 — Nghìn ngày thái bình: thức ăn dồi dào (550), sức tải 550 (tối đa 600), vựa thóc trù phú, lễ hội mùa gặt, đại yến và hãm mật độ êm dịu.
- **theocracy** 🔮 — Thời đại Khối Cầu: tôn sùng các Đồ đằng thiêng liêng, đại đền rực sáng, thần tích hiển linh, đốn ngộ 3 chiều, công đồng tôn giáo và dâng nộp đức tin.
- **warlords** ⚔️ — Quần hùng tranh bá: chinh phạt đế chế, cướp bóc kho lương, chiếm đoạt nhà cửa, thôn tính lãnh thổ và thiết lập khối liên minh phòng thủ.
- **chaos** 🔥 — Thú săn hung dữ bủa vây, huyết chiến đẫm máu, cháy rừng, động đất, dịch bệnh liên miên và thời tiết biến đổi khôn lường.
- **extinction** 💀 — Nạn đói cùng cực (120 thức ăn), mùa đông giá buốt (0.30×), phơi sương gió kiệt quệ, thử thách sức chống chịu của xã hội trước bờ vực diệt vong.
- **boom** 🚀 — Đại thịnh vượng: sinh sản bùng nổ, 440 thức ăn, sức tải 800 (tối đa 850) phục vụ thử nghiệm các siêu đô thị sầm uất.

Sử dụng: `curl -X POST localhost:8000/api/presets/balance?reset=true` hoặc chọn trực tiếp trên Bảng Khối Cầu.

## Cân bằng nội môi động & Cơ chế phòng chống diệt vong

Flatland tích hợp hai cơ chế phản hồi khép kín tự động nhằm đảm bảo trật tự dài hạn:

### 1. Cơ chế hãm mềm phụ thuộc mật độ quá tải ($\xi$)
Khi dân số $N$ vượt quá sức tải môi trường $K_{cap}$, tỷ lệ vượt ngưỡng $\xi = (N - K_{cap}) / K_{cap}$ đóng vai trò như chiếc phanh phi tuyến tính:
- **Kìm hãm sinh sản**: $R_{birth} = R_0 / (1 + \text{damping\_steepness} \cdot \xi^2)$
- **Áp lực trao đổi chất do chật chội**: $M_{decay} = M_0 \cdot (1 + \text{crowding\_stress\_mult} \cdot \xi)$
- **Căng thẳng tài nguyên**: Tốc độ sinh trưởng và phát tán hạt giống chậm lại tương ứng với mức độ bão hòa sinh thái.

### 2. Cơ chế cứu trợ diệt vong & Phép Màu Khai Thế ($\eta$)
Khi dân số sụt giảm xuống dưới ngưỡng an toàn $K_{safe} = K_{cap} \times \text{safeguard\_relief\_ratio}$, các cấp độ cứu trợ khẩn cấp sẽ kích hoạt:
- **Cấp 1 ($\eta \le 0.5$)**: Cứu tế nạn đói, giảm mức tiêu hao năng lượng trao đổi chất tới 40%, đẩy nhanh cây lớn lên tới 60%.
- **Cấp 2 ($\eta > 0.5$)**: Cứu trợ nguy cấp, giảm một nửa thời gian chờ sinh sản, đình chỉ việc an tử cá thể dị tật (`safeguard_morph_mercy`).
- **Cấp 3 ($N \le K_{crit}$)**: Khối Cầu can thiệp bằng Phép Màu Khai Thế (Genesis Miracle), tạo ra `safeguard_genesis_batch` sinh vật hình học hoàn hảo để cứu vãn sự diệt vong của thế giới.
""",
    "fr": r"""
# Durabilité — Équilibre Multi-Générationnel

Le monde maintient son équilibre sur des centaines de jours et permet l'essor de dynasties prospères grâce à une homéostasie écologique et sociale finement ajustée.

## Préréglages Sélectionnés

- **balance** ⚖️ (Défaut) — Équilibre idéal calibré pour **200 à 350 habitants** avec 380 unités de nourriture, capacité de 400 (max 500), guerres modérées, prédation rare, agriculture, amortissement de densité ($\xi$), sauvegarde contre l'extinction ($\eta$) et clans florissants.
- **sustainable** 🌿 — 1000 jours de paix prospère : nourriture abondante (550), capacité de charge 550 (max 600), greniers remplis, fêtes des moissons, banquets et amortissement doux.
- **theocracy** 🔮 — L'Ère de la Sphère : avatars sacrés, temples lumineux, miracles, épiphanies 3D, conciles sacrés et dîmes pieuses.
- **warlords** ⚔️ — L'affrontement des seigneurs : conquêtes impériales, pillages de greniers, prises de demeures, expansion territoriale et coalitions défensives.
- **chaos** 🔥 — Forte proportion de prédateurs, guerres meurtrières, incendies, séismes, épidémies fréquentes et saisons rapides.
- **extinction** 💀 — Famine sévère (120 nourriture), hivers rigoureux (0.30×), forte usure en extérieur, éprouvant la résistance sociétale face à l'effondrement.
- **boom** 🚀 — Reproduction effrénée, 440 nourriture, capacité de 800 (max 850) pour tester de gigantesques métropoles.

Utilisation : `curl -X POST localhost:8000/api/presets/balance?reset=true` ou via le panneau de La Sphère.

## Homéostasie Dynamique & Prévention de l'Extinction

Flatland intègre deux moteurs de rétroaction homéostatique en boucle fermée :

### 1. Amortissement Souple lié à la Densité ($\xi$)
Quand la population $N$ excède la capacité de charge $K_{cap}$, le ratio $\xi = (N - K_{cap}) / K_{cap}$ freine la surpopulation de façon non-linéaire :
- **Modération des naissances** : $R_{birth} = R_0 / (1 + \text{damping\_steepness} \cdot \xi^2)$
- **Stress métabolique de surpeuplement** : $M_{decay} = M_0 \cdot (1 + \text{crowding\_stress\_mult} \cdot \xi)$
- **Tension sur les ressources** : La régénération végétale ralentit proportionnellement à la saturation du milieu.

### 2. Sauvegardes d'Extinction & Miracles de la Genèse ($\eta$)
Lorsque la population chute sous le seuil d'alerte $K_{safe} = K_{cap} \times \text{safeguard\_relief\_ratio}$, des mesures d'urgence se déclenchent :
- **Niveau 1 ($\eta \le 0.5$)** : Secours anti-famine, dépense métabolique allégée jusqu'à 40%, accélération de la pousse végétale de 60%.
- **Niveau 2 ($\eta > 0.5$)** : Urgence critique, délai de reproduction réduit de moitié, suspension de l'euthanasie des difformes (`safeguard_morph_mercy`).
- **Niveau 3 ($N \le K_{crit}$)** : La Sphère opère un Miracle de la Genèse, créant un groupe `safeguard_genesis_batch` d'êtres réguliers pour perpétuer l'espèce.
""",
}

PERFORMANCE_MD_I18N = {
    "en": r"""
# Performance & Scale — 1000+ head @ 60 FPS

- **Zero-Allocation Spatial Hash**: Pre-allocated 1D bucket list in `world.py` eliminates tuple allocations and dictionary re-hashing per tick; `query_radius` uses squared-distance early-exit without `math.hypot`.
- **Fast Mate Discovery**: Spatial index queries nearby partners in $O(1)$ instead of $O(N^2)$ nested roster scans.
- **Snapshot Caching**: Static terrain and obstacles are pre-cached, eliminating redundant dictionary list copies on every broadcast frame.
- **Batched Canvas 2D Rendering**: Batches drawing passes by caste, plant variant, and house primitives with inline trigonometric vertex transforms, completely eliminating per-creature `ctx.save()` / `ctx.restore()` overhead (draw calls reduced from 20,000+ to ~30-50).
- **Dynamic Level of Detail (LOD)**: Zoom-dependent rendering skips fine-grained glyph text and ripples when zoomed out, maintaining 60 FPS even with dense populations.
- **Decoupled React State**: High-frequency simulation snapshots stream directly into mutable refs at 60 FPS for canvas rendering, while React virtual DOM reconciliation (HUD stats, charts) is throttled to ~6 Hz to keep the main browser thread light and responsive.
""",
    "vi": r"""
# Hiệu năng & Quy mô — Hơn 1000 thực thể @ 60 FPS

- **Bảng băm không gian Zero-Allocation**: Mảng 1 chiều cấp phát sẵn trong `world.py` loại bỏ việc tạo bộ tuple và băm lại từ điển mỗi nhịp; hàm `query_radius` sử dụng so sánh khoảng cách bình phương thoát sớm không cần gọi `math.hypot`.
- **Tìm bạn tình siêu tốc**: Truy vấn đối tác tiềm năng lân cận qua chỉ mục không gian trong thời gian $O(1)$ thay vì quét lặp lồng nhau $O(N^2)$.
- **Bộ nhớ đệm ảnh chụp (Snapshot Caching)**: Địa hình tĩnh và công trình được nạp sẵn vào bộ nhớ đệm, loại bỏ việc sao chép danh sách cấu trúc thừa thãi trong mỗi khung hình truyền phát.
- **Vẽ gộp nhóm Canvas 2D (Batched Canvas 2D)**: Gom nhóm các lượt vẽ theo giai tầng, biến thể cây và nhà ở với phép biến đổi lượng giác nội dòng, loại bỏ hoàn toàn chi phí `ctx.save()` / `ctx.restore()` cho từng cá thể (lệnh vẽ giảm từ hơn 20.000 xuống còn ~30-50).
- **Mức độ chi tiết động (Dynamic LOD)**: Hiển thị phụ thuộc tỷ lệ thu phóng, tự động lược bỏ văn bản danh tính và gợn sóng khi nhìn xa, bảo toàn độ mượt mà 60 FPS ngay cả khi dân số dày đặc.
- **Tách biệt trạng thái React**: Ảnh chụp trạng thái mô phỏng tần số cao truyền thẳng vào tham chiếu biến đổi (mutable refs) ở tốc độ 60 FPS cho Canvas, trong khi giao diện React (thống kê HUD, đồ thị) được điều tiết ở tần số ~6 Hz giúp trình duyệt nhẹ nhàng và phản hồi tức thì.
""",
    "fr": r"""
# Performance & Échelle — Plus de 1000 individus @ 60 FPS

- **Hachage Spatial sans Allocation** : Une grille 1D pré-allouée dans `world.py` supprime les allocations de tuples et le re-hachage à chaque tick ; `query_radius` emploie un test de distance au carré sans `math.hypot`.
- **Recherche Rapide de Partenaires** : La recherche de partenaires via l'index spatial s'effectue en $O(1)$ au lieu d'un balayage quadratique $O(N^2)$.
- **Mise en Cache des Instantanés** : Le décor statique et les obstacles sont mis en cache, supprimant la duplication inutile de listes à chaque trame diffusée.
- **Rendu Groupé Canvas 2D** : Regroupement des passes de dessin par caste, plante et structure avec transformations trigonométriques directes, éliminant le coût de `ctx.save()` / `ctx.restore()` par individu (appels de tracé réduits de plus de 20 000 à ~30-50).
- **Niveau de Détail Dynamique (LOD)** : L'affichage adapte les détails selon le zoom (omission des glyphes fins en vue éloignée), assurant un 60 FPS constant même en forte densité.
- **État React Découplé** : Le flux haute fréquence alimente directement des références mutables à 60 FPS pour le Canvas, tandis que le rafraîchissement React (HUD, graphiques) est régulé à ~6 Hz pour préserver la fluidité de l'interface.
""",
}

FLATLAND_BOOK_COMPARISON_MD_I18N = {
    "en": r"""
# Flatland: The Novella vs. The Simulation

A comparative study between **Edwin A. Abbott’s 1884 satirical classic *Flatland: A Romance of Many Dimensions*** and this autonomous artificial life simulation.

---

## 1. Caste, Geometry & Social Hierarchy

| Dimension | Abbott’s Book (*Flatland*, 1884) | Our Application (*Flatland Simulator*) |
| :--- | :--- | :--- |
| **Hierarchy Principle** | *"Configuration makes the man."* Social status is strictly determined by the number of sides and regularity of angles. | Entities inherit exact geometric castes based on vertex count (N-gons) and regularity. |
| **Women (Lines)** | Straight lines with no angular width. Because they are practically invisible head-on and razor-sharp, they are legally required to make a continuous "peace cry" and use dedicated side doors. | Rendered as 1D segments (`shape: 'line'`). Distinct agility, movement, and domestic shelter dynamics. |
| **Working Class / Soldiers** | Isosceles triangles with narrow, sharp vertex angles (dangerous, volatile, prone to rebellions). | **Soldiers** (`#ff7b72`): Sharp combatants with boosted attack, military discipline, and perimeter defense behavior. |
| **Artisans & Middle Class** | Equilateral triangles (3 equal sides) — stable and respectable tradespeople. | **Artisans** (3–4 sides, `#f2cc60`): Farmers, foragers, and builders responsible for harvesting and maintaining houses. |
| **Gentlemen & Professionals** | Squares (4 sides) and Pentagons (5 sides) — the middle/upper administrative classes. | **Gentlemen** (4 sides, `#ffa657`) and **Professionals** (5 sides, `#d2a8ff`): Administrative and specialized roles. |
| **Nobility** | Hexagons (6 sides) and higher polygons — aristocrats and statesmen. | **Nobles** (6–8 sides, `#79c0ff`): High influence and lineage priority. |
| **Priesthood (Circles)** | Polygons with so many sides (≥ 24 to hundreds) that their vertices are imperceptible, forming smooth circles. They govern religion, law, and morality. | **Priests** (≥ 24 sides, `#e6edf3`): Emit soothing auras, heal injured or infected clanmates, and resist disease. |

---

## 2. The "Law of Nature" & Generational Ascent

- **In the Book**:
  - Abbott establishes the **"Law of Upward Development"**: A male child of a regular polygon almost always inherits **one more side** than his father (e.g., a Square fathers a Pentagon, whose son becomes a Hexagon), lifting the lineage toward circular Priesthood over generations.
  - Rare **"Irregulars"** (whose sides/angles do not match) are viewed as societal threats and sent to state institutions or executed.
- **In the App**:
  - **Generational Evolution**: Offspring inherit ancestral traits with a probabilistic side increment (`sides += 1`), simulating the gradual generational ascent toward circular perfection.
  - **Irregularity & Demotion**: Entities that develop genetic irregularity or undergo trauma have their irregularity tracked and are judged/demoted or marked with distinct visual indicators.
  - **Dynastic Lineage**: The Family Tree tracks mother, father, and generational pedigree across decades of world history.

---

## 3. Sight Recognition, Weather & Perception

- **In the Book**:
  - In a 2D world, all inhabitants look like flat lines from the edge!
  - In the **Foggy South**, Flatlanders rely on **"Sight Recognition"** — judging the angle and distance of an approaching polygon by how quickly its edges fade into the atmospheric fog.
  - In the **Clear North**, they must rely on **"Feeling"** (touching vertices with fingertips).
- **In the App**:
  - **Dynamic Weather Engine**: Simulates **Clear**, **Fog**, **Rain**, and **Storm** states.
  - **Atmospheric Vision**: Fog and storms dynamically restrict creature vision radii (`sight_radius`), forcing entities to rely on local spatial queries and nearby auditory alarms (`signals`).
  - **Day/Night & Lighting**: The ambient illuminance curves shift through dawn, noon, dusk, and pitch-black night, restricting wandering and driving creatures into their shelters.

---

## 4. Housing, Settlements & Territorial Architecture

- **In the Book**:
  - Houses are strictly pentagonal or hexagonal, with specific entrances: a smaller rear entrance for lines (women) and a main entrance for polygons.
- **In the App**:
  - **Settlement Economy**: Houses are physical 2D structures with precise interior boundaries, oriented doors (`north`, `east`, `south`, `west`), and bed capacities.
  - **Single Main House Invariant**: Each clan establishes exactly **one Main House / HQ** (the Leader's residence) with surrounding outpost shelters.
  - **Shelter Dynamics**: Creatures seek refuge inside houses to sleep at night, protect against winter frostbite, heal from chills, and educate infant offspring.
  - **Doorway Entry & Exit Navigation**: Creatures calculate vector standoff waypoints to transition smoothly through doorway openings when entering shelter at dusk or exiting to forage and explore at dawn, preventing indoor wall trapping.

---

## 5. Clan Diplomacy, Totems & Autonomous Society

While Abbott’s book portrays a centralized Victorian government, our app layers an **evolutionary social simulation**:
- **Sacred Avatars & Specialization**: Each clan bears one of the 8 Sacred Avatars of the Sphere (⭕ Radiant Circle, ⚡ Celestial Strike, 👁️ All-Seeing Vertex, 🛡️ Indomitable Monolith, 🌿 Sacred Spiral, ⚖️ Cosmic Scales, 🌀 Dimensional Rift, 🕯️ Eternal Hearth), each granting a distinct divine buff and biasing the clan's balance of warriors, farmers, and scavengers.
- **Diplomacy, Tributes & War**: Dynamic clan relations with wars, peace treaties, tribute subjugation, and schisms.
- **Personal Autonomy & Inventory**: Independent personality archetypes (Brave, Cautious, Altruistic, Greedy, Explorer, Builder) with personal foraging baskets, tools (spears, crowns, herb poultices), and emergency self-preservation eating.

---

## 6. The Higher Dimension: The User as "The Sphere"

The most profound connection between the app and the book is the **role of the user**:
- In *Flatland*, the protagonist **A Square** is visited by **A Sphere** from the 3D *Spaceland*, who can look down from the Z-axis, see into locked rooms, view internal organs, and manipulate the 2D world with god-like omnipresence.
- **In our App**:
  - **You are the Sphere (God)**: As the observer on your screen, you look down on Flatland from Spaceland (the third dimension).
  - **The Sphere Panel**: You hold the power of The Sphere to alter the "Laws of Nature" in real-time — toggling famine, changing food growth multipliers, curing or spreading plagues, introducing winter freezes, or blessing clans with prosperity.
""",
    "vi": r"""
# Xứ Phẳng: Đối Chiếu Tiểu Thuyết Abbott & Bản Mô Phỏng

Khảo cứu đối chiếu giữa danh tác châm biếm kinh điển năm 1884 của **Edwin A. Abbott — *Flatland: A Romance of Many Dimensions*** và hệ sinh thái mô phỏng sự sống nhân tạo tự hành.

---

## 1. Giai tầng, Hình học & Trật tự Xã hội

| Khía cạnh | Tiểu thuyết của Abbott (*Flatland*, 1884) | Bản Mô Phỏng (*Flatland Simulator*) |
| :--- | :--- | :--- |
| **Nguyên lý giai tầng** | *"Hình thù làm nên địa vị."* Thứ bậc xã hội được ấn định nghiêm ngặt bởi số lượng cạnh và độ đều của các góc. | Các cá thể kế thừa giai tầng hình học chính xác dựa trên số đỉnh (đa giác N cạnh) và tính đều đặn. |
| **Phụ nữ (Đoạn thẳng)** | Là các đoạn thẳng không có độ dày góc. Do gần như vô hình khi nhìn trực diện và sắc bén như dao cạo, họ buộc phải liên tục cất tiếng ngâm nga hòa bình và đi lối cửa phụ. | Hiển thị dưới dạng đoạn thẳng 1D (`shape: 'line'`). Cực kỳ linh hoạt, có tập tính di chuyển và nhu cầu trú ẩn đặc thù. |
| **Binh lính & Tiền đạo** | Tam giác cân với góc đỉnh rất nhọn hoắt (hung hãn, hiếu chiến, mầm mống bạo loạn). | **Binh sĩ** (`#ff7b72`): Chiến binh sắc bén với sát thương cao, kỷ luật tác chiến và tuần tra bảo vệ biên giới. |
| **Thợ thủ công & Trung lưu** | Tam giác đều (3 cạnh bằng nhau) — tầng lớp lao động và buôn bán ổn định, đáng kính. | **Nghệ nhân** (3–4 cạnh, `#f2cc60`): Nông dân, thợ hái lượm và thợ xây phụ trách thu hoạch mùa màng, chăm sóc vựa lương và sửa chữa nhà cửa. |
| **Thân sĩ & Quý tộc** | Hình vuông (4 cạnh) và Ngũ giác (5 cạnh) — tầng lớp quản lý hành chính và học giả. | **Thân sĩ** (4 cạnh, `#ffa657`) & **Học giả** (5 cạnh, `#d2a8ff`): Đảm nhiệm vai trò quản lý và điều hành cộng đồng. |
| **Giới Quý tộc thượng lưu** | Lục giác (6 cạnh) và các đa giác bậc cao — giới quý tộc và nhà lập pháp. | **Quý tộc** (6–8 cạnh, `#79c0ff`): Có tiếng nói xã hội lớn và vị thế ưu tiên trong gia phả dòng tộc. |
| **Tế tư (Hình tròn)** | Đa giác có vô số cạnh (≥ 24 đến hàng trăm) đến mức các đỉnh tạo thành đường tròn trơn láng. Nắm giữ luật pháp và đức tin. | **Tế tư** (≥ 24 cạnh, `#e6edf3`): Tỏa ánh hào quang chữa lành vết thương, xua tan mầm bệnh cho đồng tộc và miễn nhiễm dịch tễ. |

---

## 2. "Định luật Tự nhiên" & Sự Thăng tiến Dòng tộc

- **Trong Tiểu thuyết**:
  - Abbott xây dựng **"Định luật Thăng tiến"**: Con trai của đa giác đều hầu như luôn thừa hưởng **nhiều hơn cha mình một cạnh** (ví dụ: Hình Vuông sinh ra Ngũ Giác, rồi sinh ra Lục Giác), nâng tầm dòng dõi hướng tới sự hoàn hảo tròn trịa của Tế tư qua nhiều đời.
  - Những cá thể **"Dị dạng"** (các cạnh/góc bất thường) bị coi là mối họa cho xã hội và bị cách ly hoặc xử tử.
- **Trong Ứng dụng Mô phỏng**:
  - **Tiến hóa thế hệ**: Thế hệ con kế thừa các đặc tính từ cha mẹ với xác suất tăng thêm cạnh (`sides += 1`), mô phỏng chân thực sự thăng tiến dần dần qua các thời kỳ lịch sử.
  - **Dị tật & Giáng cấp**: Sinh vật phát triển dị tật gen sẽ bị theo dõi độ dị hình, bị giáng cấp và có biểu tượng nhận diện trực quan riêng.
  - **Gia phả dòng họ**: Cây phả hệ lưu giữ chi tiết cha, mẹ và dòng dõi qua hàng trăm ngày lịch sử thế giới.

---

## 3. Nhận biết Thị giác, Thời tiết & Cảm nhận Sương mù

- **Trong Tiểu thuyết**:
  - Trong thế giới 2 chiều phẳng, mọi cư dân nhìn ngang đều chỉ là những đoạn dẹt!
  - Ở **Miền Nam Sương mù**, cư dân dùng **"Nhận biết bằng mắt"** — phán đoán góc và khoảng cách của một đa giác qua tốc độ mờ dần của các cạnh trong sương mù.
  - Ở **Miền Bắc Trong trẻo**, họ phải dựa vào **"Sờ soạng"** (chạm vào các đỉnh bằng đầu ngón tay).
- **Trong Ứng dụng Mô phỏng**:
  - **Động cơ thời tiết động**: Tái hiện 4 trạng thái **Quang đãng**, **Sương mù**, **Mưa** và **Giông bão**.
  - **Tầm nhìn khí quyển**: Sương mù và giông bão trực tiếp thu hẹp bán kính quan sát, buộc sinh vật phải dựa vào tiếng hú báo động và cảm biến khoảng cách gần.
  - **Ngày & Đêm**: Cường độ chiếu sáng thay đổi tự nhiên qua bình minh, giữa trưa, hoàng hôn và đêm tối mịt mùng, thúc đẩy sinh vật tìm đường về nhà trú ẩn.

---

## 4. Nhà ở, Khu định cư & Kiến trúc Lãnh thổ

- **Trong Tiểu thuyết**:
  - Nhà ở bắt buộc phải có hình ngũ giác hoặc lục giác với cửa riêng: cửa nhỏ phía sau cho phụ nữ (đoạn thẳng) và cửa chính cho nam giới đa giác.
- **Trong Ứng dụng Mô phỏng**:
  - **Kinh tế định cư**: Nhà cửa là cấu trúc vật lý 2D với ranh giới bên trong, cửa ra vào có hướng (`bắc`, `đông`, `nam`, `tây`) và số chỗ ngủ giới hạn.
  - **Bản doanh duy nhất**: Mỗi thị tộc sở hữu đúng **một Nhà Chính / Bản doanh** (nơi ở của Thủ lĩnh) cùng các chòi trú ẩn vệ tinh bao quanh.
  - **Nhu cầu trú ẩn**: Sinh vật tìm về nhà để ngủ khi màn đêm buông xuống, tránh rét buốt mùa đông, hồi phục sinh lực và nuôi dưỡng con non.
  - **Điều hướng qua cửa**: Sinh vật tính toán điểm đứng chờ thông minh để di chuyển mượt mà qua khe cửa khi trời tối và tỏa ra tìm thức ăn khi bình minh, không bị kẹt vào vách tường.

---

## 5. Bang giao Thị tộc, Đồ đằng & Xã hội Tự hành

Khác với mô hình chính quyền tập quyền thời Victoria trong sách, ứng dụng triển khai **mô phỏng xã hội tiến hóa tự sinh**:
- **Đồ đằng Thần thánh**: Mỗi thị tộc tôn sùng một trong 8 Đồ đằng thiêng của Khối Cầu (⭕ Sung Túc, ⚡ Nộ Thần, 👁️ Toàn Tri, 🛡️ Trường Tồn, 🌿 Tái Sinh, ⚖️ Cân Bằng, 🌀 Huyền Bí, 🕯️ Bếp Ấm), định hình thiên hướng nghề nghiệp và sự chuyên môn hóa giữa các chiến binh, nông dân và thợ hái lượm.
- **Bang giao, Cống nạp & Chiến tranh**: Quan hệ thị tộc diễn tiến linh hoạt với hòa ước đình chiến, liên minh tương trợ, cống nạp bảo hộ và nguy cơ phân liệt nội bộ.
- **Tính cách độc lập**: Các hình mẫu tính cách (Dũng cảm, Thận trọng, Vị tha, Tư lợi, Khai phá, Xây dựng) mang túi cói cá nhân, công cụ (giáo, thuốc đắp, vương miện) và phản xạ tự cứu mình khi nguy cấp.

---

## 6. Chiều Không Gian Cao Hơn: Người Dùng Trong Vai "Khối Cầu"

Mối liên kết sâu sắc nhất giữa ứng dụng và tiểu thuyết chính là **vai trò của người quan sát**:
- Trong tiểu thuyết, nhân vật chính **A Square (Hình Vuông)** được viếng thăm bởi **Khối Cầu (A Sphere)** đến từ *Không Gian 3D (Spaceland)*, người có thể nhìn từ trục Z xuống, thấy được bên trong các căn phòng kín, nhìn thấu tâm can và thao túng mặt phẳng 2D như một Đấng Sáng Tạo toàn năng.
- **Trong Ứng dụng của chúng ta**:
  - **Bạn chính là Khối Cầu (Chúa)**: Khi nhìn vào màn hình, bạn đang quan sát Xứ Phẳng từ chiều không gian thứ ba.
  - **Bảng Khối Cầu**: Bạn nắm giữ quyền năng tối thượng để ban bố "Thiên luật Tự nhiên" theo thời gian thực — tạo ra nạn đói, điều chỉnh sinh trưởng thức ăn, phát tán hoặc chữa lành dịch bệnh, mang mùa đông buốt giá đến hoặc ban phước lành thịnh vượng cho các thị tộc.
""",
    "fr": r"""
# Flatland : Le Roman vs. La Simulation

Étude comparative entre le classique satirique d'**Edwin A. Abbott (1884), *Flatland: A Romance of Many Dimensions*** et cette simulation autonome de vie artificielle.

---

## 1. Castes, Géométrie & Hiérarchie Sociale

| Dimension | Livre d'Abbott (*Flatland*, 1884) | Notre Simulation (*Flatland Simulator*) |
| :--- | :--- | :--- |
| **Principe hiérarchique** | *"La configuration fait l'homme."* Le rang social est strictement déterminé par le nombre de côtés et la régularité des angles. | Les entités héritent de castes géométriques précises basées sur leur nombre de sommets (N-gones) et leur régularité. |
| **Femmes (Lignes)** | Lignes droites sans épaisseur angulaire. Invisibles de face et acérées comme des lames, elles doivent émettre un cri de paix continu et emprunter des portes dédiées. | Représentées comme des segments 1D (`shape: 'line'`). Remarquablement agiles, avec une dynamique de déplacement et d'abri spécifique. |
| **Ouvriers / Soldats** | Triangles isocèles aux angles sommitaux étroits et tranchants (dangereux, instables, enclins aux révoltes). | **Soldats** (`#ff7b72`) : Combattants aux attaques perçantes, discipline martiale et patrouilles défensives aux frontières. |
| **Artisans & Classe moyenne** | Triangles équilatéraux (3 côtés égaux) — marchands et travailleurs respectables et stables. | **Artisans** (3–4 côtés, `#f2cc60`) : Fermiers, cueilleurs et bâtisseurs chargés des récoltes et de l'entretien des demeures. |
| **Gentlemen & Professionnels** | Carrés (4 côtés) et Pentagones (5 côtés) — classes administratives et bourgeoises dirigeantes. | **Gentlemen** (4 côtés, `#ffa657`) et **Professionnels** (5 côtés, `#d2a8ff`) : Rôles d'administration et de gestion spécialisée. |
| **Noblesse** | Hexagones (6 côtés) et polygones supérieurs — aristocrates et hommes d'État influents. | **Nobles** (6–8 côtés, `#79c0ff`) : Haute influence et priorité dans la pérennité de la lignée. |
| **Clergé (Cercles)** | Polygones aux sommets si innombrables (≥ 24 à plusieurs centaines) qu'ils forment des cercles parfaits. Dirigent religion et morale. | **Prêtres** (≥ 24 côtés, `#e6edf3`) : Émettent une aura apaisante, soignent leurs alliés et résistent naturellement aux épidémies. |

---

## 2. La "Loi de la Nature" & L'Ascension Générationnelle

- **Dans le Livre** :
  - Abbott pose la **"Loi du Progrès Ascendant"** : Le fils d'un polygone régulier gagne presque toujours **un côté de plus** que son père (un Carré engendre un Pentagone, dont le fils sera Hexagone), élevant la lignée vers la perfection circulaire.
  - Les rares **"Irréguliers"** (aux angles asymétriques) sont perçus comme une menace publique et enfermés ou éliminés.
- **Dans l'Application** :
  - **Évolution générationnelle** : La progéniture hérite des traits ancestraux avec une probabilité d'accroissement (`sides += 1`), illustrant l'ascension historique vers le cercle.
  - **Irrégularité & Déclassement** : Les entités développant des mutations asymétriques voient leur anomalie mesurée et signalée visuellement.
  - **Généalogie dynastique** : L'arbre généalogique retrace pères, mères et filiations sur des décennies d'histoire du monde.

---

## 3. Reconnaissance Visuelle, Météo & Perception

- **Dans le Livre** :
  - Dans un monde 2D, tous les habitants ressemblent vus de profil à de simples lignes !
  - Dans le **Sud Brumeux**, les Flatlandais pratiquent la **"Reconnaissance Visuelle"** — estimant l'angle et la distance d'un polygone selon la rapidité avec laquelle ses bords se fondent dans le brouillard.
  - Dans le **Nord Clair**, ils doivent recourir au **"Palper"** (toucher les sommets du bout des doigts).
- **Dans l'Application** :
  - **Moteur météo dynamique** : Alterne entre **Ciel dégagé**, **Brouillard**, **Pluie** et **Tempête**.
  - **Vision atmosphérique** : La brume et les orages réduisent drastiquement le champ visuel des créatures, les obligeant à se fier aux alarmes acoustiques de proximité.
  - **Cycle Jour/Nuit** : La luminosité varie de l'aube au crépuscule jusqu'à l'obscurité totale, guidant les créatures vers la sécurité de leurs foyers.

---

## 4. Habitats, Colonies & Architecture Territoriale

- **Dans le Livre** :
  - Les maisons sont obligatoirement pentagonales ou hexagonales, avec des entrées distinctes pour les femmes et les hommes.
- **Dans l'Application** :
  - **Économie coloniale** : Les maisons sont des bâtisses 2D concrètes avec portes orientées (`nord`, `est`, `sud`, `ouest`) et nombre de lits limité.
  - **Demeure Principale Unique** : Chaque clan fonde exactement **une Demeure Principale / QG** (siège du chef) entourée d'abris secondaires.
  - **Fonction du refuge** : Les créatures y dorment la nuit, s'y protègent des gelées d'hiver, s'y soignent et y éduquent leurs petits.
  - **Navigation de franchissement** : Les créatures calculent des points de passage fluides pour franchir les seuils sans rester bloquées contre les parois.

---

## 5. Diplomatie de Clan, Totems & Société Évolutive

Au-delà de l'État victorien centralisé d'Abbott, l'application met en scène une **société évolutive vivante** :
- **Totems & Spécialisation** : Vénération de l'un des 8 Avatars Sacrés de la Sphère (⭕ Radiant Circle, ⚡ Celestial Strike, 👁️ All-Seeing Vertex, 🛡️ Indomitable Monolith, 🌿 Sacred Spiral, ⚖️ Cosmic Scales, 🌀 Dimensional Rift, 🕯️ Eternal Hearth), orientant les vocations du clan.
- **Diplomatie, Tributs & Conflits** : Relations mouvantes entre clans incluant traités, guerres de conquête, pillages de greniers et scissions.
- **Autonomie individuelle** : Tempéraments personnalisés (Brave, Prudent, Altruiste, Avare, Explorateur, Bâtisseur) dotés de paniers individuels et d'outils façonnés.

---

## 6. La Dimension Supérieure : L'Utilisateur est "La Sphère"

Le lien le plus fondamental entre le livre et l'application réside dans le **statut de l'utilisateur** :
- Dans *Flatland*, le protagoniste **A Square** reçoit la visite d'une **Sphère** venue de *Spaceland*, capable de contempler le monde depuis l'axe vertical, de voir à travers les portes closes et de modifier l'univers 2D avec une toute-puissance céleste.
- **Dans notre Application** :
  - **Vous êtes La Sphère (Dieu)** : Devant votre écran, vous observez Flatland depuis la troisième dimension.
  - **Le Panneau de La Sphère** : Vous détenez le pouvoir de réécrire les "Lois de la Nature" en direct — déclencher des famines, moduler la fertilité, éradiquer ou propager les fléaux et guider les clans vers la gloire.
""",
}


# ---------------------------------------------------------------------
# GodLaws Hints Translations (72 parameters)
# ---------------------------------------------------------------------
LAW_HINTS_I18N = {
    "en": {
        "boundary": "World border topology: wrap (seamless toroidal loop) vs clamp (solid collision walls).",
        "food_count": "Living food plants maintained across the world (summer ×1.2, winter ×0.5).",
        "energy_max": "Maximum metabolic energy capacity an organism can store (10–500).",
        "energy_decay_per_tick": "Baseline metabolic burn rate per tick without food (0.025).",
        "energy_from_food": "Base energy yield from harvesting a mature plant (berry 48, grass 32, mushroom 24, poison 8).",
        "plant_variants_enabled": "Master switch enabling botanical biodiversity across 6 distinct functional plant species.",
        "plant_growth_rate": "How fast sprouted plants mature into harvestable food (0.045).",
        "plant_spread_rate": "Probability per tick that a mature plant drops seeds into adjacent fertile ground (0.006).",
        "nutrient_cycle_rate": "Acceleration of plant growth near decomposing corpses (0.65) — death nourishes new life.",
        "poison_rate": "Probability a new wild sprout is poisonous (-30 HP damage on ingestion).",
        "food_decay_enabled": "Enables mature plants to naturally wither over time and fertilize the living soil.",
        "food_lifespan_ticks": "Ticks a mature plant lives before naturally withering into the living soil grid (8000).",
        "agriculture_enabled": "Enables seed gathering, cultivated farm plots (2× growth, 2.5× yield), irrigation furrows, and tending.",
        "granaries_enabled": "Enables communal settlement granaries to stockpile grain and berries against winter.",
        "granary_capacity": "Units of food a settlement granary can store (400) — feasts fire at ≥80% capacity.",
        "perceive_radius": "Base perception sight radius (16) — scaled by caste (Woman 0.8×, Priest 1.35×), night (0.6×), and fog (0.6×).",
        "eat_radius": "Physical contact distance required to consume a plant, corpse, or prey item (1.4).",
        "hungry_ratio": "Energy threshold (≤35%) feeding normalized energy into neural network input slot 0 to trigger foraging.",
        "starving_ratio": "Severe energy threshold (≤15%) triggering desperation sprint and pulsing survival distress.",
        "steer_turn": "Maximum heading angular turn agility per tick, scaled by creature moment of inertia Izz.",
        "birth_enabled": "Master switch enabling reproduction, mating, and generational ascendance.",
        "lifespan_mult": "Multiplier scaling all caste lifespans (Woman: 4,800 ticks → Priest: 9,000 ticks).",
        "adult_age": "Ticks required for an infant/juvenile to mature into a sexually fertile adult (220).",
        "birth_rate": "Base reproduction probability per eligible adult mating pair per tick (0.28).",
        "carrying_capacity": "Population density threshold above which fertility gradually fades (-1 = auto).",
        "max_population": "Hard global population cap preventing any new births until density declines (-1 = auto).",
        "mutation_rate": "Probability a newborn son deviates ±1 side from classical caste inheritance (0.05).",
        "sex_ratio": "Probability a newborn child is a son (ascending polygon) vs daughter (agile line) (0.50).",
        "max_sides": "Upper limit on regular polygon vertex ascendance (up to Priest / Circle status) (24).",
        "euthanasia_threshold": "Irregularity threshold; deformed infants exceeding this are consumed at adulthood (0.70).",
        "mutation_sigma": "Gaussian mutation standard deviation (σ) applied to genome weights during crossover (0.08).",
        "crossover_rate": "Probability of uniform 50/50 parental genome blending during sexual reproduction (0.50).",
        "morphology_annealing_enabled": "Master switch for geometric physics — polar (r,φ) annealing, SAT polygon collision, and trait baking.",
        "annealing_decay_generations": "Generations over which polar morphology annealing decays from Abbott templates to free evolution (150).",
        "disease_enabled": "Master switch for infectious pathogen outbreaks and contagion transmission.",
        "disease_outbreak_rate": "Spontaneous plague outbreak probability per tick during crowded conditions (0.00006).",
        "disease_rate": "Contagion transmission probability per tick within contact range (0.035).",
        "disease_energy_drain": "Metabolic energy drained per tick from actively infected creatures (0.05).",
        "disease_lethality": "Direct health (HP) damage dealt per tick to actively diseased creatures (0.18).",
        "weather_enabled": "Master switch for dynamic meteorological cycles (sun, rain, fog, storms).",
        "sleep_enabled": "Enables diurnal sleep cycles, house resting, and oral lore transfer after dark.",
        "day_length": "Total duration in ticks of a single diurnal day/night cycle (1200).",
        "season_length": "Duration in ticks of each season (Spring, Summer, Autumn, Winter) (12000).",
        "winter_food_mult": "Winter seasonal food abundance multiplier (0.70 gentle, 0.50 harsh, 0.30 extinction).",
        "night_sight_mult": "Perception radius multiplier during night ticks for non-nocturnal castes (0.60).",
        "weather_change_rate": "Frequency of meteorological transitions between clear, rain, fog, and storm (0.002).",
        "weather_sickness_enabled": "Enables exposure chill and hypothermia when caught unsheltered in wet or freezing weather.",
        "chill_drain": "Direct health drain per tick when chilled outdoors without shelter (0.18).",
        "shelter_enabled": "Master switch for house claiming, door navigation, and roof protection.",
        "exposure_drain": "Health and energy drain per tick when outdoors during harsh weather (0.025).",
        "house_capacity": "Bed capacity inside a settlement hall (12); excess members sleep outdoors.",
        "house_decay_ticks": "Ticks before an abandoned, roofless house crumbles into ruins (10000).",
        "rest_recovery_mult": "Health regeneration multiplier when sleeping indoors under a roof (2.0).",
        "territory_enabled": "Enables clan boundary markings, territory defence, and trespass penalties.",
        "territory_radius": "Radius of clan territorial influence around settlement houses (16).",
        "trespass_decay": "Diplomatic relation points lost per tick when a rival clan enters marked territory (0.15).",
        "max_clans": "Maximum number of sovereign clans spawned during world initialization (-1 = auto).",
        "totems_enabled": "Enables Sacred Avatar totem blessings for each clan settlement.",
        "succession_enabled": "Enables dynamic governance leadership transfers on chieftain death.",
        "communication_enabled": "Enables vocalizations, alarm chirps, peace hums, and emotional thought bubbles.",
        "knowledge_enabled": "Enables spatial memory, waypoint mapping, and rumor broadcasting among kin.",
        "schism_enabled": "Enables internal clan fractures when members starve or lack shelter.",
        "schism_threshold": "Dissatisfaction fraction (hunger, homelessness) triggering a factional clan schism (0.40).",
        "war_enabled": "Enables inter-clan warfare, tactical raids, and territorial conquest.",
        "attack_damage": "Base damage dealt by soldiers and warriors in inter-clan battles (32.0).",
        "predation_enabled": "Enables carnivorous predator-prey ecology and hunting dynamics.",
        "predator_ratio": "Fraction of population spawned as predatory carnivores hunting prey (0.02).",
        "hunt_radius": "Aggro detection radius within which carnivores and war parties acquire targets (16.0).",
        "bite_damage": "Combat damage dealt per carnivore attack or predatory strike (28.0).",
        "energy_from_prey": "Caloric energy extracted from slaying and eating a prey creature (45.0).",
        "fear_radius": "Distance at which herbivores and vulnerable castes detect threats and execute evasion (12.0).",
        "coalitions_enabled": "Enables mutual defensive alliances and diplomatic treaties between friendly clans.",
        "coalition_threshold": "Diplomatic trust score required for two friendly clans to form a defensive coalition (40).",
        "leader_decisions_enabled": "Enables chieftain governance bylaws (rationing, martial law, war declarations).",
        "resource_sharing_enabled": "Enables communal settlement larders and altruistic basket food sharing.",
        "larder_capacity": "Energy capacity of settlement communal food stores where surplus is shared (300).",
        "cannibalism_enabled": "Enables desperate consumption of the living during extreme starvation.",
        "eat_kin_enabled": "Allows consumption of deceased or weak clanmates at the cost of tribal exile and feuds.",
        "cannibalism_energy": "Energy gained by starving creatures resorting to eating fallen kin or rivals (45.0).",
        "theology_enabled": "Enables the 8 Sacred Avatars, shrines, temples, miracles, and divine tithes.",
        "tithe_rate": "Fraction of energy devout worshippers offer at shrines each dawn & dusk to build clan faith (0.04).",
        "temple_faith_cost": "Faith points required to consecrate a glowing Temple of the Sphere (400.0).",
        "age_enabled": "Enables historical epoch progression (Golden Age, Ice Age, Age of Chaos, Age of Plague).",
        "age_length": "Duration in ticks per world historical epoch (50000).",
        "culture_enabled": "Enables traditions, governance archetypes, and cultural diffusion.",
        "culture_spread_rate": "Rate at which allied clans sharing borders adopt common cultural traits and beliefs (0.0005).",
        "rivers_enabled": "Enables water channels, fords, water currents, bridges, and dams.",
        "river_count": "Number of procedural river channels carved across the terrain at world generation (2).",
        "relief_enabled": "Enables topographical elevation, slope inertia, cliffs, and road packing.",
        "structural_enabled": "Enables weather wear on buildings, builder repairs, and roof collapse into rubble.",
        "earthquake_enabled": "Enables seismic tremors that shake terrain and damage weakened structures.",
        "earthquake_rate": "Frequency of seismic quakes that crack buildings and shake terrain (0.00008).",
        "lightning_enabled": "Enables real lightning strikes during storms that ignite fires and damage creatures.",
        "lightning_strike_rate": "Frequency of deadly electrical arc strikes during thunder storms (0.0015).",
        "wildfire_enabled": "Enables combustive flame propagation across dense vegetation and forests.",
        "fire_rate": "Probability per tick that a mature plant ignites during dry spells or lightning strikes (0.00008).",
        "disaster_enabled": "Enables cataclysmic meteors, floods, and natural world disturbances.",
        "disaster_rate": "Stochastic probability of catastrophic environmental disasters (0.0003).",
        "anomaly_count": "Number of mysterious spatial anomaly zones altering local physics (3).",
        "door_clearance": "Width multiplier for house doorways relative to the largest creature size (1.5).",
    },
    "vi": {
        "boundary": "Quy tắc ranh giới thế giới: 'wrap' (vòng xuyến vô tận) vs 'clamp' (tường chắn vật lý).",
        "food_count": "Lượng cây thức ăn / lương thực thế giới duy trì liên tục (mùa hè ×1.2, mùa đông ×0.5).",
        "energy_max": "Mức năng lượng tối đa một cá thể có thể tích lũy (10–500).",
        "energy_decay_per_tick": "Tiêu hao năng lượng trao đổi chất cơ bản mỗi nhịp khi nhịn đói (0.025).",
        "energy_from_food": "Năng lượng thu được khi thu hoạch cây chín (quả mọng 48, cỏ 32, nấm 24, cây độc 8).",
        "plant_variants_enabled": "Công tắc chính bật tính đa dạng với 6 loài thực vật chuyên biệt.",
        "plant_growth_rate": "Tốc độ cây non sinh trưởng thành cây có thể thu hoạch (0.045).",
        "plant_spread_rate": "Xác suất mỗi nhịp cây chín phát tán hạt giống sang ô đất màu mỡ lân cận (0.006).",
        "nutrient_cycle_rate": "Gia tốc mọc cây quanh xác thực thể phân hủy (0.65) — cái chết bồi đắp cho sự sống.",
        "poison_rate": "Xác suất chồi non mọc ra là cây có độc (-30 sinh lực khi ăn phải).",
        "food_decay_enabled": "Phân hủy xác thực vật già cỗi bồi bổ dưỡng chất cho đất.",
        "food_lifespan_ticks": "Thời gian tồn tại của cây trưởng thành trước khi tự rũ bỏ thân xác vào đất (8000 nhịp).",
        "agriculture_enabled": "Khai phá nông canh, luống cày xới (lớn nhanh 2×, sản lượng 2.5×), rãnh tưới và làm cỏ.",
        "granaries_enabled": "Dựng vựa thóc lớn tại làng để tích trữ lương thực vượt qua mùa đông.",
        "granary_capacity": "Dung tích tối đa của vựa lương (400) — mở đại yến khi đầy ≥80%.",
        "perceive_radius": "Bán kính quan sát chuẩn (16) — biến đổi theo giai tầng (Nữ giới 0.8×, Tế tư 1.35×), đêm tối (0.6×) và sương mù (0.6×).",
        "eat_radius": "Khoảng cách tiếp xúc vật lý tối thiểu để ăn thức ăn, rỉa xác hoặc bắt mồi (1.4).",
        "hungry_ratio": "Ngưỡng đói (≤35%) đưa tín hiệu vào mạng nơ-ron để thôi thúc tìm kiếm thức ăn.",
        "starving_ratio": "Ngưỡng đói lả nguy kịch (≤15%) kích hoạt nước rút sinh tồn và phát tín hiệu báo nguy.",
        "steer_turn": "Góc quay đầu tối đa mỗi nhịp, tính toán theo quán tính hình thể của sinh vật.",
        "birth_enabled": "Công tắc chính cho phép giao phối, sinh sản và kế thừa dòng dõi.",
        "lifespan_mult": "Hệ số nhân thọ mệnh cho mọi giai tầng (Nữ giới: 4.800 nhịp → Tế tư: 9.000 nhịp).",
        "adult_age": "Số nhịp cần thiết để con non trưởng thành và có thể sinh sản (220).",
        "birth_rate": "Tỷ lệ thụ thai cơ bản của mỗi cặp đôi trưởng thành đủ no mỗi nhịp (0.28).",
        "carrying_capacity": "Ngưỡng sức tải môi trường: vượt ngưỡng này tỷ lệ sinh sẽ suy giảm (-1 = tự động).",
        "max_population": "Trần dân số cứng: ngăn chặn mọi ca sinh mới cho đến khi mật độ giảm (-1 = tự động).",
        "mutation_rate": "Xác suất con trai sinh ra bị đột biến lệch ±1 cạnh so với quy luật thừa kế (0.05).",
        "sex_ratio": "Xác suất sinh con trai (đa giác tiến hóa) so với con gái (đoạn thẳng linh hoạt) (0.50).",
        "max_sides": "Giới hạn số cạnh tối đa của đa giác đều (chạm ngưỡng Tế tư / Hình tròn) (24).",
        "euthanasia_threshold": "Ngưỡng dị hình; cá thể vượt mốc này sẽ bị loại trừ khi vừa trưởng thành (0.70).",
        "mutation_sigma": "Độ lệch chuẩn Gaussian (σ) áp dụng lên trọng số não bộ khi lai phối (0.08).",
        "crossover_rate": "Tỷ lệ hòa trộn đồng đều 50/50 bộ gen cha mẹ trong quá trình thụ thai (0.50).",
        "morphology_annealing_enabled": "Công tắc chính cho vật lý hình học — ủ nhiệt (r,φ), va chạm SAT và giải phóng hình thể.",
        "annealing_decay_generations": "Số thế hệ để quá trình ủ nhiệt chuyển từ khuôn mẫu Abbott sang tiến hóa tự do (150).",
        "disease_enabled": "Công tắc chính cho phép dịch bệnh bùng phát và lây nhiễm trong quần thể.",
        "disease_outbreak_rate": "Xác suất tự bùng phát dịch bệnh mỗi nhịp khi mật độ dân cư ngột ngạt (0.00006).",
        "disease_rate": "Tỷ lệ lây truyền mầm bệnh mỗi nhịp khi tiếp xúc gần cá thể nhiễm bệnh (0.035).",
        "disease_energy_drain": "Năng lượng bị hao hụt mỗi nhịp do lâm bệnh nặng (0.05).",
        "disease_lethality": "Sát thương rút máu trực tiếp mỗi nhịp do độc lực của bệnh tật (0.18).",
        "weather_enabled": "Công tắc chính cho chu kỳ khí tượng biến đổi (nắng, mưa, sương, giông).",
        "sleep_enabled": "Tập tính ngủ nghỉ ban đêm, trú ẩn trong nhà và truyền thụ kinh nghiệm lúc đêm tối.",
        "day_length": "Tổng số nhịp của một chu kỳ ngày đêm trọn vẹn (1200).",
        "season_length": "Độ dài của một mùa (Xuân, Hạ, Thu, Đông) theo số nhịp (12000).",
        "winter_food_mult": "Hệ số khan hiếm thức ăn khi mùa đông buốt giá tràn về (0.70 nhẹ, 0.50 khốc liệt, 0.30 tuyệt diệt).",
        "night_sight_mult": "Hệ số thu hẹp tầm nhìn trong bóng đêm đối với sinh vật ban ngày (0.60).",
        "weather_change_rate": "Tần suất biến chuyển giữa các trạng thái thời tiết (0.002).",
        "weather_sickness_enabled": "Bị nhiễm hàn khí và hạ thân nhiệt khi đứng ngoài mưa gió buốt lạnh không có mái che.",
        "chill_drain": "Tổn hao sinh lực mỗi nhịp khi cơ thể bị nhiễm lạnh ngoài trời (0.18).",
        "shelter_enabled": "Công tắc chính cho cơ chế nhận nhà, điều hướng qua cửa và mái che bảo vệ.",
        "exposure_drain": "Tổn hại máu và năng lượng mỗi nhịp khi phơi mình ngoài sương gió mùa đông (0.025).",
        "house_capacity": "Số lượng chỗ nằm trong mỗi căn nhà (12); thành viên vượt mức phải ngủ ngoài trời.",
        "house_decay_ticks": "Thời gian một căn nhà bỏ hoang sụp đổ thành phế tích (10000 nhịp).",
        "rest_recovery_mult": "Hệ số tăng tốc hồi sinh lực khi ngủ trong nhà ấm có che chắn (2.0).",
        "territory_enabled": "Xác lập ranh giới lãnh thổ thị tộc, bảo vệ biên cương và phạt xâm nhập.",
        "territory_radius": "Bán kính tầm ảnh hưởng lãnh thổ tỏa ra từ các căn nhà của thị tộc (16).",
        "trespass_decay": "Điểm bang giao bị khấu trừ mỗi nhịp khi kẻ thù tự tiện bước vào lãnh địa (0.15).",
        "max_clans": "Số lượng thị tộc tối đa được khởi tạo khi lập thế giới mới (-1 = tự động).",
        "totems_enabled": "Cho phép thị tộc đón nhận phước lành từ một trong 8 Đồ đằng Thần thánh thiêng liêng.",
        "succession_enabled": "Tự động bầu chọn người tài kế vị quyền lãnh đạo khi thủ lĩnh băng hà.",
        "communication_enabled": "Phát tiếng gọi tìm mồi, hú báo nguy, ngâm nga hòa bình và bóng suy nghĩ.",
        "knowledge_enabled": "Ghi nhớ địa hình thức ăn, mối hiểm họa và truyền miệng tin tức trong thị tộc.",
        "schism_enabled": "Thành viên đói kém và mất chỗ ở sẽ nổi dậy ly khai lập tộc mới.",
        "schism_threshold": "Tỷ lệ bất mãn thổi bùng làn sóng ly khai chia rẽ nội bộ (0.40).",
        "war_enabled": "Chiến tranh liên thị tộc, tập kích cướp lương và mở rộng bờ cõi.",
        "attack_damage": "Sát thương cơ bản do binh sĩ gây ra trong chiến trận (32.0).",
        "predation_enabled": "Kích hoạt chuỗi thức ăn thú săn mồi ăn thịt và con mồi ăn cỏ.",
        "predator_ratio": "Tỷ lệ sinh ra thú ăn thịt hung hãn trong tự nhiên (0.02).",
        "hunt_radius": "Bán kính săn mồi và truy sát mục tiêu của thú ăn thịt (16.0).",
        "bite_damage": "Sát thương từ vết cắn xé của thú ăn thịt (28.0).",
        "energy_from_prey": "Năng lượng calo hấp thụ được khi săn gục và ăn thịt con mồi (45.0).",
        "fear_radius": "Khoảng cách thú ăn cỏ đánh hơi thấy nguy hiểm để bỏ chạy tháo thân (12.0).",
        "coalitions_enabled": "Ký kết hòa ước liên minh phòng thủ tương trợ giữa các thị tộc thân thiện.",
        "coalition_threshold": "Điểm tin cậy ngoại giao tối thiểu để hai tộc kết nghĩa liên minh phòng thủ (40).",
        "leader_decisions_enabled": "Thủ lĩnh ban bố sắc lệnh (phát chẩn lúc đói, thiết quân luật, phát động chiến tranh).",
        "resource_sharing_enabled": "Kho lương chung tại bản doanh giúp sẻ chia miếng ăn và cứu đói nhau.",
        "larder_capacity": "Trữ lượng năng lượng tối đa của kho lương tập thể thị tộc (300).",
        "cannibalism_enabled": "Ăn thịt đồng loại trong tuyệt vọng khi rơi vào đường cùng của nạn đói.",
        "eat_kin_enabled": "Cho phép ăn thịt người cùng dòng tộc (phải trả giá bằng lưu đày và thù hận muôn đời).",
        "cannibalism_energy": "Năng lượng thu được khi ăn thịt một cá thể đồng loại lúc đói lả (45.0).",
        "theology_enabled": "Thần học 8 Đồ đằng, dựng đền miếu, dâng lễ vật đức tin và thần tích hiển linh.",
        "tithe_rate": "Tỷ lệ năng lượng tín đồ dâng hiến vào lúc bình minh và hoàng hôn để tích lũy đức tin (0.04).",
        "temple_faith_cost": "Lượng đức tin cần thiết để nâng cấp đền miếu thành Đại Đền Khối Cầu (400.0).",
        "age_enabled": "Tiến trình các thời đại lịch sử lớn (Hoàng Kim, Băng Hà, Hỗn Thoát, Dịch Bệnh).",
        "age_length": "Độ dài của một thời đại lịch sử tính theo số nhịp (50000).",
        "culture_enabled": "Bản sắc văn hóa, tập tục và sự lan tỏa tập quán giữa các thị tộc.",
        "culture_spread_rate": "Tốc độ truyền bá tập tục văn hóa sang các thị tộc đồng minh cận kề (0.0005).",
        "rivers_enabled": "Dòng sông tự nhiên ngăn cách đôi bờ, kèm vùng nước xiết, bãi cạn và cầu bắc ngang.",
        "river_count": "Số nhánh sông được kiến tạo tự nhiên ngăn chia bản đồ (2).",
        "relief_enabled": "Địa hình trập trùng: dốc cao tốn sức, vách đá gây ngã gãy xương, đường mòn đi nhanh.",
        "structural_enabled": "Công trình bị hao mòn do bão lốc, thợ xây sửa chữa, sập thành đống đổ nát.",
        "earthquake_enabled": "Địa chấn làm rung chuyển mặt đất, làm đổ sập những căn nhà ọp ẹp.",
        "earthquake_rate": "Tần suất xảy ra địa chấn rung chuyển mặt đất mỗi nhịp (0.00008).",
        "lightning_enabled": "Tia sét đánh trúng mặt đất trong cơn giông, phát hỏa và sát thương sinh mệnh.",
        "lightning_strike_rate": "Tần suất tia sét giáng xuống mặt đất trong cơn giông bão (0.0015).",
        "wildfire_enabled": "Cháy rừng lan truyền nhanh chóng qua các thảm cỏ và rừng rậm rạp.",
        "fire_rate": "Xác suất thực vật bốc cháy khi khô hạn hoặc bị sét giáng trúng (0.00008).",
        "disaster_enabled": "Đại thảm họa bất ngờ như mưa thiên thạch hoặc hồng thủy dâng trào.",
        "disaster_rate": "Xác suất ngẫu nhiên giáng xuống đại thảm họa thiên nhiên (0.0003).",
        "anomaly_count": "Số lượng vùng dị thường không gian làm biến dạng quy luật vật lý cục bộ (3).",
        "door_clearance": "Tỷ lệ độ rộng cửa nhà so với kích thước cá thể lớn nhất (1.5).",
    },
    "fr": {
        "boundary": "Topologie des frontières : 'wrap' (boucle toroïdale continue) vs 'clamp' (parois rigides infranchissables).",
        "food_count": "Nombre de plantes nourricières maintenues dans le monde (été ×1.2, hiver ×0.5).",
        "energy_max": "Capacité métabolique maximale emmagasinable par un organisme (10–500).",
        "energy_decay_per_tick": "Taux de dépense métabolique de base par tick sans apport alimentaire (0.025).",
        "energy_from_food": "Énergie tirée de la récolte d'une plante mûre (baie 48, herbe 32, champignon 24, poison 8).",
        "plant_variants_enabled": "Interrupteur principal activant la biodiversité parmi 6 espèces végétales fonctionnelles.",
        "plant_growth_rate": "Vitesse de maturation des jeunes pousses en nourriture récoltable (0.045).",
        "plant_spread_rate": "Probabilité par tick qu'une plante mûre dissémine des graines sur un sol fertile adjacent (0.006).",
        "nutrient_cycle_rate": "Accélération de la pousse près des carcasses en décomposition (0.65) — la mort nourrit la vie.",
        "poison_rate": "Probabilité qu'une pousse sauvage soit toxique (-30 PV de dégâts en cas d'ingestion).",
        "food_decay_enabled": "Permet aux plantes mûres de flétrir naturellement et d'enrichir l'humus du sol.",
        "food_lifespan_ticks": "Durée de vie en ticks d'une plante mûre avant son retour à la terre (8000).",
        "agriculture_enabled": "Active la collecte de semences, parcelles labourées (croissance 2×, récolte 2.5×) et sarclage.",
        "granaries_enabled": "Permet aux colonies d'aménager des greniers collectifs pour stocker grains et baies.",
        "granary_capacity": "Capacité de stockage d'un grenier communal (400) — banquets à partir de ≥80% de remplissage.",
        "perceive_radius": "Rayon de vision de base (16) — modulé par caste (Femme 0.8×, Prêtre 1.35×), nuit (0.6×) et brume (0.6×).",
        "eat_radius": "Distance physique de contact requise pour ingérer une plante, dépouille ou proie (1.4).",
        "hungry_ratio": "Seuil de faim (≤35%) envoyant un signal au réseau neuronal pour déclencher la quête de vivres.",
        "starving_ratio": "Seuil de famine critique (≤15%) provoquant une course d'urgence et des appels de détresse.",
        "steer_turn": "Agilité angulaire maximale par tick, proportionnelle au moment d'inertie Izz.",
        "birth_enabled": "Interrupteur général commandant la reproduction, l'accouplement et l'ascendance de caste.",
        "lifespan_mult": "Multiplicateur de longévité pour toutes les castes (Femme : 4 800 ticks → Prêtre : 9 000 ticks).",
        "adult_age": "Ticks requis pour qu'un nouveau-né atteigne la maturité reproductrice (220).",
        "birth_rate": "Probabilité d'engendrement par couple adulte éligible et par tick (0.28).",
        "carrying_capacity": "Seuil de densité démographique au-delà duquel la fertilité faiblit progressivement (-1 = auto).",
        "max_population": "Plafond démographique absolu interdisant toute naissance tant que la densité reste trop forte (-1 = auto).",
        "mutation_rate": "Probabilité qu'un fils dévie de ±1 côté par rapport à la caste paternelle (0.05).",
        "sex_ratio": "Probabilité qu'un nouveau-né soit un fils (polygone ascendant) ou une fille (ligne agile) (0.50).",
        "max_sides": "Limite supérieure du nombre de côtés des polygones réguliers (jusqu'au statut de Prêtre) (24).",
        "euthanasia_threshold": "Seuil d'irrégularité ; les nouveau-nés difformes excédant ce taux sont éliminés à l'âge adulte (0.70).",
        "mutation_sigma": "Écart-type gaussien (σ) appliqué aux poids synaptiques lors du brassage génétique (0.08).",
        "crossover_rate": "Probabilité de recombinaison génétique équilibrée 50/50 entre les parents (0.50).",
        "morphology_annealing_enabled": "Interrupteur de physique géométrique — recuit polaire (r,φ), collision SAT et propriétés corporelles.",
        "annealing_decay_generations": "Générations requises pour que le recuit passe des gabarits d'Abbott à l'évolution libre (150).",
        "disease_enabled": "Interrupteur général des épidémies infectieuses et de la contagion interindividuelle.",
        "disease_outbreak_rate": "Probabilité d'émergence spontanée de peste en milieu surpeuplé par tick (0.00006).",
        "disease_rate": "Probabilité de transmission de la contagion à portée de contact (0.035).",
        "disease_energy_drain": "Perte d'énergie métabolique par tick pour chaque individu contaminé (0.05).",
        "disease_lethality": "Dégâts directs de santé (PV) infligés par tick par l'infection (0.18).",
        "weather_enabled": "Interrupteur des cycles météorologiques dynamiques (soleil, pluie, brume, orages).",
        "sleep_enabled": "Active le sommeil nocturne, le repos sous abri et la tradition orale à la nuit tombée.",
        "day_length": "Durée totale en ticks d'un cycle jour/nuit complet (1200).",
        "season_length": "Durée en ticks de chaque saison (Printemps, Été, Automne, Hiver) (12000).",
        "winter_food_mult": "Multiplicateur hivernal d'abondance alimentaire (0.70 doux, 0.50 rude, 0.30 critique).",
        "night_sight_mult": "Facteur réducteur de vision nocturne pour les castes diurnes (0.60).",
        "weather_change_rate": "Fréquence des transitions entre temps clair, pluie, brume et orage (0.002).",
        "weather_sickness_enabled": "Active l'hypothermie et le refroidissement en cas d'exposition prolongée aux intempéries.",
        "chill_drain": "Perte de vie directe par tick subie lors d'une exposition au froid sans toit (0.18).",
        "shelter_enabled": "Interrupteur de revendication des maisons, franchissement de portes et toitures.",
        "exposure_drain": "Perte d'énergie et de vie lors des intempéries hors de tout abri (0.025).",
        "house_capacity": "Nombre de places de couchage dans une halle (12) ; l'excédent dort à la belle étoile.",
        "house_decay_ticks": "Ticks avant qu'une maison abandonnée et sans toit ne tombe en ruine (10000).",
        "rest_recovery_mult": "Facteur de régénération de santé lors du sommeil sous un toit protecteur (2.0).",
        "territory_enabled": "Active le bornage frontalier, la garde territoriale et les pénalités d'intrusion.",
        "territory_radius": "Rayon d'influence territoriale d'un clan autour de ses habitations (16).",
        "trespass_decay": "Dégradation diplomatique par tick lorsqu'un clan rival franchit la frontière (0.15).",
        "max_clans": "Nombre maximal de clans souverains créés lors de la génération du monde (-1 = auto).",
        "totems_enabled": "Active les bénédictions des Totems d'Avatars Sacrés pour chaque colonie clanique.",
        "succession_enabled": "Permet la passation dynamique du commandement clanique à la mort du chef.",
        "communication_enabled": "Active les vocalises, cris d'alarme, chants de paix et bulles d'états d'âme.",
        "knowledge_enabled": "Active la mémoire spatiale, la cartographie des repères et les rumeurs partagées.",
        "schism_enabled": "Déclenche des scissions internes lorsque les membres manquent de vivres ou d'abris.",
        "schism_threshold": "Taux d'insatisfaction (faim, sans-abri) déclenchant une scission de faction (0.40).",
        "war_enabled": "Active les conflits armés entre clans rivaux, raids tactiques et conquêtes.",
        "attack_damage": "Dégâts de base infligés par les soldats lors des affrontements de clans (32.0).",
        "predation_enabled": "Active la dynamique proie-prédateur et le régime carnivore.",
        "predator_ratio": "Proportion de la population naissant avec l'instinct carnivore de chasse (0.02).",
        "hunt_radius": "Rayon de détection d'agression dans lequel prédateurs et guerriers ciblent leurs proies (16.0).",
        "bite_damage": "Dégâts physiques causés par morsure ou attaque prédatrice (28.0).",
        "energy_from_prey": "Gain calorique extrait de la capture et dévoration d'une proie (45.0).",
        "fear_radius": "Distance à laquelle herbivores et castes vulnérables fuient face au danger (12.0).",
        "coalitions_enabled": "Autorise les pactes de défense mutuelle et alliances diplomatiques entre clans amis.",
        "coalition_threshold": "Score de confiance mutuelle requis pour sceller une coalition défensive (40).",
        "leader_decisions_enabled": "Permet au chef de décréter des lois d'urgence (rationnement, loi martiale, guerre).",
        "resource_sharing_enabled": "Active les greniers collectifs et le partage altruiste de nourriture via les paniers.",
        "larder_capacity": "Capacité calorique des réserves collectives où sont déposés les surplus (300).",
        "cannibalism_enabled": "Autorise la consommation désespérée de chair en cas de famine extrême.",
        "eat_kin_enabled": "Permet de dévorer les dépouilles d'alliés au prix du bannissement et de vendettas.",
        "cannibalism_energy": "Énergie retirée de la consommation d'un congénère ou d'un ennemi terrassé (45.0).",
        "theology_enabled": "Active les 8 Avatars Sacrés, oratoires, temples, miracles et offrandes pieuses.",
        "tithe_rate": "Fraction d'énergie offerte aux sanctuaires à l'aube et au crépuscule pour la foi (0.04).",
        "temple_faith_cost": "Points de foi indispensables pour ériger un Temple resplendissant de la Sphère (400.0).",
        "age_enabled": "Active la succession des ères historiques (Âge d'Or, Glaciaire, Chaos, Peste).",
        "age_length": "Durée en ticks de chaque époque historique du monde (50000).",
        "culture_enabled": "Active les traditions, archétypes de gouvernement et diffusion culturelle.",
        "culture_spread_rate": "Vitesse d'adoption des traits culturels et dogmes entre clans voisins (0.0005).",
        "rivers_enabled": "Active les cours d'eau, gués, courants aquatiques, ponts et barrages.",
        "river_count": "Nombre de canaux fluviaux procéduraux façonnés à l'initialisation du monde (2).",
        "relief_enabled": "Active le dénivelé topographique, l'inertie des pentes, falaises et sentiers tassés.",
        "structural_enabled": "Active la dégradation des bâtiments par la météo, réparations et décombres.",
        "earthquake_enabled": "Permet des secousses sismiques ébranlant le relief et endommageant les édifices.",
        "earthquake_rate": "Fréquence des tremblements de terre lézardant les sols et structures (0.00008).",
        "lightning_enabled": "Déclenche de véritables éclairs orageux embrasant la végétation et blessant les êtres.",
        "lightning_strike_rate": "Fréquence des arcs électriques foudroyants lors des violentes tempêtes (0.0015).",
        "wildfire_enabled": "Permet la propagation d'incendies dévastateurs dans les forêts et fourrés secs.",
        "fire_rate": "Probabilité par tick qu'une plante prenne feu par temps sec ou foudre (0.00008).",
        "disaster_enabled": "Active météores cataclysmiques, crues subites et catastrophes majeures.",
        "disaster_rate": "Probabilité aléatoire d'avènement de calamités environnementales (0.0003).",
        "anomaly_count": "Nombre de zones d'anomalies spatiales déformant la physique locale (3).",
        "door_clearance": "Coefficient d'élargissement des ouvertures de portes selon la taille des créatures (1.5).",
    },
}

# ---------------------------------------------------------------------
# Re-export content translations from wiki_content_i18n
# ---------------------------------------------------------------------
from .wiki_content_i18n import (
    CODEBASE_MAP_MD_I18N,
    CONFIG_OPS_MD_I18N,
    CURL_EXAMPLES_I18N,
    DATA_MODEL_MD_I18N,
    HOW_IT_WORKS_MD_I18N,
)