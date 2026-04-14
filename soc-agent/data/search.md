# SOC Strategy Agent — Search Memory

> **Last Updated:** 2026-04-14T03:04:06.857866+00:00
> **Total Findings:** 34 | **Confirmed Facts:** 6 | **Open Gaps:** 15

---

## 📊 Search Coverage

| Topic | Depth | Last Searched | Summary |
|-------|-------|--------------|---------|
| Apple | 🔴 Low | 2026-04-14 | API rate limits blocked fresh retrieval again; only prior knowledge available —  |
| Qualcomm | 🟡 Medium | 2026-04-14 | Snapdragon X2 Elite Extreme and X2 Plus confirmed with 80 TOPS Hexagon NPU and 3 |
| MediaTek | 🟡 Medium | 2026-04-14 | Filogic 8000 confirmed as world's first Wi-Fi 8 CPE SoC (CES 2026); Filogic 660/ |
| Chinese OEMs | 🟡 Medium | 2026-04-14 | OPPO launched 'Xiaobu Claw' AI agent (April 2026) with cross-device command supp |
| Samsung | 🔴 Low | 2026-04-14 | API rate limits again blocked fresh retrieval; prior knowledge confirms Exynos 2 |
| Android Ecosystem | 🟢 High | 2026-04-14 | Google Gemma 4 + LiteRT-LM + AppFunctions define the Android on-device agent inf |
| Network Operators | 🟡 Medium | 2026-04-14 | NVIDIA ARC Pro ecosystem secured commitments from BT, Deutsche Telekom, Ericsson |
| AI Agent Apps | 🟡 Medium | 2026-04-14 | Google Agent Skills is first fully on-device multi-step autonomous agent on Andr |
| 6G Technology | 🟡 Medium | 2026-04-14 | ITU-R WP5D reached consensus on 20 IMT-2030 TPRs (7 new for 6G) in Feb 2026, for |
| CPE Devices | 🟡 Medium | 2026-04-14 | MediaTek Filogic 8000 leads Wi-Fi 8 CPE; Qualcomm X2 Plus extends to CPE/gateway |

---

## 🔑 Key Findings (de-duplicated)

1. ITU-R WP5D reached consensus on 20 IMT-2030 Technical Performance Requirements (7 new 6G-specific) in February 2026; formal ITU-R approval expected December 2026
2. 3GPP Rel-20 follows dual-track architecture (5G-Advanced + 6G research); Stage 1 frozen June 2025; Rel-21 full 6G spec work begins March 2027 at earliest — creating 18-24 month SoC vendor option window
3. 6G air interface specification not yet frozen — SoC design teams face 'blind flight' risk on modem architecture decisions before 2027
4. China completed Phase 1 6G key technology tests and holds 300+ technology reserves, raising risk of parallel China vs. ITU-R/3GPP 6G standard tracks
5. NVIDIA Aerial RAN Computer (ARC) Pro secured commitments from BT, Deutsche Telekom, Ericsson, Nokia, SK Telecom, SoftBank, T-Mobile at MWC 2026 for AI-native 6G platform
6. NTT DOCOMO completed world's first outdoor 6G demonstration with AI-RAN integration
7. Indosat Ooredoo Hutchison achieved Southeast Asia's first AI-RAN Layer 3 5G call
8. SoftBank demonstrated Large Telecom Model (LTM) translating natural-language operational goals into real-time 5G/6G network configuration
9. T-Mobile plans to evaluate NVIDIA Aerial RAN Computer (ARC) Pro technology in 2026
10. NVIDIA-led AI-RAN ecosystem lock-in risk: baseband SoC vendors risk being demoted to 'connectivity pipes' if ARC Pro ecosystem solidifies — must define irreplaceable roles (low-latency control plane, local sensing processing)
11. Google launched Gemma 4 (April 2026) for complex reasoning and autonomous tool-calling, positioned as the Android on-device agent AI standard
12. Google released LiteRT-LM open-source edge LLM inference framework, replacing MediaPipe LLM Inference API, with lower latency and privacy-first design
13. Android officially introduced AppFunctions mechanism, transitioning OS to 'Agent-First' architecture
14. Android Bench LLM leaderboard shows on-device AI agent task completion rates of 16-72%, indicating significant optimization opportunity for NPU-capable SoCs
15. Gemma 4 + LiteRT-LM + AppFunctions collectively define the minimum hardware threshold for Android on-device agent inference — NPU-deficient SoCs face clear agent experience disadvantage
16. MediaTek Filogic 8000 announced at CES 2026 as world's first Wi-Fi 8 CPE SoC platform
17. MediaTek MWC 2026 demo showed on-device generative AI CPE with local data governance and privacy protection, plus intelligent multi-channel management and interference suppression
18. MediaTek Filogic 660/680 in mass deployment with Tier-1 operators across North America, Europe, and Asia for fiber gateway and Wi-Fi 7 CPE
19. CPE market transformation signal: operator token-based billing models emerging; CPE transitioning from connectivity devices to local AI compute nodes — 18-month window before design lock-out
20. Qualcomm Snapdragon X2 Elite Extreme and X2 Elite launched at 2025 Snapdragon Summit: 80 TOPS Hexagon NPU, up to 18-core Oryon CPU, 3nm process, targeting 2026 device launches
21. Qualcomm Snapdragon X2 Plus (6-core and 10-core variants) features 80 TOPS NPU and new Snapdragon Guardian enterprise remote management capability, lowering CPE/gateway OEM design barriers
22. OPPO launched 'Xiaobu Claw' (小布爪) AI agent in April 2026 — third Chinese OEM to release phone AI agent — supporting call summarization and cross-device commands
23. OPPO AndesGPT deployed smart after-sales service in 20 countries across 13 languages
24. OPPO launched 'Omni' full-modal on-device AI model at MWC 2026
25. Xiaomi announced annual self-designed chip release cadence; HyperAI integrates Google Gemini and plans overseas expansion via EV vertical
26. Xiaomi MiMo-V2-Flash open-source reasoning model demonstrates strong performance in coding and agent scenarios
27. Chinese OEM structural shift: dependency on SoC vendors moving from 'AI capability provider' to 'compute infrastructure provider' — SoC vendors must offer deep NPU toolchain lock-in (model optimization SDK, TEE secure execution) to maintain customer retention
28. Google Agent Skills is the first application to run fully on-device multi-step autonomous agent workflows on Android, powered by Gemma 4, supporting multi-step planning, autonomous action, offline code generation, and audio-visual processing
29. AndesGPT cloud-edge collaborative framework open-sourced, signaling shift from tool-type to proactive AI agent applications
30. Geopolitical dual-track 6G risk: China's parallel 6G standardization path vs. ITU-R/3GPP may force SoC vendors to maintain separate modem IP licensing and compliance architectures for China and non-China markets
31. cmWave (7-15 GHz) confirmed as primary 6G frequency band; sub-THz semiconductor strategy remains undefined — pre-positioning cmWave RF front-end IP is actionable near-term
32. AI-native hardware compute partitioning for 6G RAN not yet defined in standards — represents both a risk and an IP pre-positioning opportunity for baseband SoC vendors
33. Apple on-device AI continues to rely on Neural Engine in A/M-series SoCs; A19 roadmap specifics unconfirmed due to retrieval failure
34. Samsung Exynos 2500 uses Samsung 4nm process with NPU differentiation focus; Exynos 2600 AI NPU competitive positioning vs. Snapdragon/Dimensity remains uncovered

---

## ✅ Confirmed Facts (appeared in 2+ runs)

- Apple differentiates on-device AI via proprietary Neural Engine in A/M-series Apple Silicon — consistent across multiple runs
- Samsung Galaxy AI strategy relies on Exynos NPU as key differentiator — referenced consistently but details unconfirmed from live data
- MediaTek Filogic series is in active mass deployment with global Tier-1 operators for Wi-Fi CPE — confirmed by deployment data this run
- On-device AI agent compute demand is structurally increasing, driven by multi-step autonomous workflows requiring sustained NPU throughput — confirmed by both Android ecosystem and Chinese OEM data
- 6G standardization timeline: ITU-R IMT-2030 formal approval expected December 2026; 3GPP Rel-21 full work March 2027 — confirmed via WP5D consensus data
- NPU performance is becoming the primary competitive differentiator for flagship and upper-mid SoCs in 2026-2027 — confirmed across Qualcomm, MediaTek, Android ecosystem, and Chinese OEM findings

---

## ⚠️ Information Gaps (not yet covered)

- [ ] Apple A19 / M-series AI SoC roadmap signals — retrieval blocked by API rate limits for second consecutive run
- [ ] Samsung Exynos 2600 AI NPU architecture and competitive strategy vs. Snapdragon X Elite / Dimensity — retrieval blocked again
- [ ] Broadcom CPE SoC (BCM6XXX series) AI integration roadmap — minimal public information, significant competitive blind spot
- [ ] Qualcomm X Elite / X Plus CPE-specific deployment pipeline: operator design wins, integration roadmap beyond spec sheet
- [ ] 6G air interface specification detail — not yet frozen; SoC design team decision points remain undefined pending 3GPP Rel-21
- [ ] Sub-THz (above 100 GHz) semiconductor and packaging strategy for 6G — no vendor has publicly committed
- [ ] AI-native hardware compute partitioning standards for 6G RAN — undefined in current 3GPP/ITU-R scope
- [ ] Geopolitical dual-track 6G: specific technical divergences between China IMT-2030 implementation and ITU-R/3GPP path
- [ ] On-device privacy regulation impact on AI SoC design (EU AI Act, US state-level laws) — not yet retrieved
- [ ] Killer app / super app AI agent monetization models and revenue-sharing with SoC vendors — not yet covered
- [ ] Network operator AI-native SoC procurement requirements beyond NVIDIA ARC Pro ecosystem (open RAN SoC specs)
- [ ] KDDI and other Asian operator 6G and AI-RAN specific technology roadmaps — only SKT/SoftBank/DOCOMO covered
- [ ] Wi-Fi 8 CPE SoC competitive timeline: when Qualcomm and Broadcom plan to respond to MediaTek Filogic 8000 first-mover advantage
- [ ] ISP bundling economics for AI gateway CPE — operator token billing model details and SoC margin impact
- [ ] Xiaomi self-designed chip technical specifications and foundry partnership details

---

## 🔄 Repeated / High-Confidence Signals

- NPU TOPS as primary SoC competitive metric — appeared in Qualcomm (80 TOPS X2), MediaTek (Filogic AI), and Android ecosystem (Gemma 4 hardware floor) data consistently
- On-device privacy / local data sovereignty as CPE AI selling point — appeared in both MediaTek Filogic framing and Android LiteRT-LM positioning
- Chinese OEM AI agent capability accelerating (OPPO AndesGPT, Xiaomi HyperAI) — referenced in both Chinese OEM and AI agent app categories
- 6G as 2030 commercial target with 2027 as spec crystallization point — consistent across 6G technology and network operator findings
- NVIDIA AI-RAN ecosystem (ARC Pro) as dominant platform with multiple operator commitments — confirmed in both network operator and 6G technology findings

---

## 🎯 Next Search Priorities

> The next search run will focus on these topics first.

1. 6G air interface and AI-RAN hardware compute partitioning — most critical unresolved SoC architecture decision point before 2027 Rel-21 launch; actionable IP pre-positioning window closing
2. Broadcom CPE SoC AI roadmap (BCM6XXX) — largest competitive blind spot in CPE SoC landscape given MediaTek and Qualcomm coverage; essential for complete market map
3. Apple A19 / Samsung Exynos 2600 AI SoC roadmap — two flagship SoC vendors with zero live data retrieved across two consecutive runs; must resolve retrieval or use alternative sources
4. On-device privacy regulation (EU AI Act, US state laws) impact on SoC design requirements — regulatory forcing function that will shape NPU architecture, TEE requirements, and product segmentation
5. Wi-Fi 8 CPE competitive response timeline (Qualcomm / Broadcom vs. MediaTek Filogic 8000) and ISP AI gateway bundling economics — 18-month design window signal makes this an urgent strategic monitoring priority
