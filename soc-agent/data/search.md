# SOC Strategy Agent — Search Memory

> **Last Updated:** 2026-04-13T17:18:29.384417+00:00
> **Total Findings:** 30 | **Confirmed Facts:** 5 | **Open Gaps:** 15

---

## 📊 Search Coverage

| Topic | Depth | Last Searched | Summary |
|-------|-------|--------------|---------|
| Apple | 🔴 Low | 2026-04-13 | Limited signal: MacBook Neo adopts MediaTek Wi-Fi/BT chip over Broadcom, marking |
| Qualcomm | 🟡 Medium | 2026-04-13 | Qualcomm faces intensifying competition from MediaTek across Wi-Fi, SoC and tele |
| MediaTek | 🟢 High | 2026-04-13 | MediaTek leads CPE AI with Wi-Fi 8 + 5G-A + 50 TOPS NPU platform; Airoha is firs |
| Chinese OEMs | 🔴 Low | 2026-04-13 | Direct intelligence on Xiaomi HyperAI, OPPO AndesGPT, vivo and Huawei AI differe |
| Samsung | 🔴 Low | 2026-04-13 | No new direct intelligence on Exynos 2600 NPU or Galaxy AI strategy this run; du |
| Android Ecosystem | 🟢 High | 2026-04-13 | Google Gemma 4 (Apr 2026) sets new on-device Agentic AI standard with E2B/E4B mo |
| Network Operators | 🟡 Medium | 2026-04-13 | MNOs (BT, Deutsche Telekom, T-Mobile, SoftBank) pivoting from connectivity to AI |
| AI Agent Apps | 🔴 Low | 2026-04-13 | Direct killer-app/super-app monetisation intelligence missing; indirect signal v |
| 6G Technology | 🟡 Medium | 2026-04-13 | 3GPP 6G study (TR 38.914) 60% complete; Release 21 timeline to be decided June 2 |
| CPE Devices | 🟢 High | 2026-04-13 | MediaTek/Airoha AI Fiber Gateway (Wi-Fi 8 + 5G-A + 50 TOPS NPU + triple open-sou |

---

## 🔑 Key Findings (de-duplicated)

1. Google Gemma 4 (Apr 2026) introduces E2B/E4B models targeting mobile/IoT edge Agentic AI, requiring multi-step reasoning and autonomous tool-calling, directly raising minimum NPU threshold for flagship SoCs toward 2026-2027
2. Google LiteRT-LM (Apr 8 2026) replaces MediaPipe LLM Inference API as the open-source edge LLM inference framework, with 400M+ Gemma series downloads signalling deep Android ecosystem entrenchment
3. Android AI Edge Gallery launches Agent Skills: fully on-device multi-step autonomous agent workflows (plan→act→verify), marking the cloud-to-edge inflection point for mobile AI agents
4. Android Bench publishes first LLM leaderboard with 16-72% task completion rate variance, establishing a public benchmark that will drive SoC NPU competitive positioning
5. Android Studio Otter 3 adds BYOM (Bring Your Own Model) and Agent Mode, supporting LM Studio/Ollama local models, further democratising on-device AI development
6. Airoha (MediaTek subsidiary) became world's first CPE SoC vendor to integrate OpenWrt, RDK-B and prplOS in a single chip platform (Mar 30 2026), with AI Fiber Gateway NPU at 50 TOPS
7. MediaTek MWC 2026: launched smart CPE platform combining world's first Wi-Fi 8 chip + 5G-A CPE with edge Gen AI; operators report 30%+ UX improvement and 20% Wi-Fi throughput gain
8. MacBook Neo teardown reveals Apple adopted MediaTek Wi-Fi/BT chip over Broadcom, marking a significant Broadcom customer loss and MediaTek ecosystem expansion into Apple supply chain
9. MediaTek deepened collaboration with Google TPU v7 Ironwood ASIC on I/O module integration, signalling strategic alignment between MediaTek silicon and Google's AI infrastructure
10. Broadcom defending North America CPE market with BCM6714/BCM6719 dual-band Wi-Fi 8 radio + embedded telemetry, but faces first substantive threat from Airoha after Lumen CPE win
11. Lumen awarded Airoha fiber CPE business in the US, giving MediaTek group its first real foothold in the North American CPE operator market against Broadcom
12. Digitimes (Apr 10 2026): MediaTek launching end-to-end challenge against Qualcomm and Broadcom across Wi-Fi, SoC and telecom markets simultaneously
13. TSMC advanced node (4/3nm) wafer loading projected to decline 10-15% driven by Chinese OEM order cuts and consumer electronics demand softness (Digitimes, Apr 7 2026)
14. Qualcomm CES 2026: showcased Snapdragon platform spanning mobile/PC/automotive with on-device AI as core; acquired Arduino and Edge Impulse to strengthen full-stack edge computing capability
15. 3GPP 6G study TR 38.914 reached 60% completion as of March 2026; Release 21 timeline decision scheduled June 2026; full specifications expected end-2028; commercial deployment 2029-2030
16. NTT DOCOMO completed world's first outdoor AI-driven RAN 6G field test, validating AI-RAN architecture at a practical level
17. NVIDIA invested $1B in Nokia to develop AI-RAN solutions; T-Mobile plans to evaluate Aerial RAN Computer (ARC) Pro in 2026
18. Six identified 6G standardisation gaps: ①Release 21 timeline unconfirmed, ②AI interface standards inconsistent (cross-vendor AI interoperability unresolved), ③geopolitical fragmentation risk (potential parallel Western 3GPP vs. China-led standards), ④spectrum allocation pending, ⑤3GPP/O-RAN coordination still maturing, ⑥AI integration in standardisation lagging hardware progress
19. Ericsson proposed 4-step AI-native network framework: mature 5G SA → secure autonomy → trusted data foundation → full-network AI, requiring AI embedded in RAN/Core/Transport/OSS-BSS layers
20. NVIDIA partnered with BT, Deutsche Telekom, T-Mobile and others to build open, software-defined, AI-native 6G platform; SoftBank demonstrated natural-language 5G/6G network configuration via 'Large Telecom Model'
21. NGMN alliance advancing tokenised billing; MNOs require networks to support AI agent collaboration (industrial robots, autonomous vehicle fleets) via on-demand dynamic private network deployment
22. ResearchAndMarkets 2026-2030 MNO report confirms Telco-to-Techco pivot: from pure connectivity to platform/API-led revenue growth, requiring CPE and mobile SoCs to natively support network-exposed APIs, tokenised QoS, and AI agent coordination
23. CPE AI transformation core drivers confirmed: decentralised Gen AI compute, local user data governance (privacy compliance), real-time traffic classification and QoS optimisation
24. Operator procurement criteria for CPE shifting from 'connection bandwidth' to 'edge AI capability', moving competitive moat from hardware specs to software ecosystem integration depth
25. Memory bandwidth identified as critical bottleneck: tension between on-device LLM/Agent inference demands and mobile power constraints; SoCs integrating HBM/LPDDR5X+ or novel memory architectures in-package gain significant differentiation
26. Open-source ecosystem control emerging as new SoC moat: Airoha's OpenWrt/RDK-B/prplOS integration and Google's LiteRT-LM dominance show that ecosystem integration depth is becoming a competitive barrier
27. Geopolitical 6G fragmentation risk identified as potential opportunity: SoCs with multi-standard-compatible architecture can position in both Western 3GPP and China-led standard ecosystems simultaneously
28. SoC vendors with early investment in AI-RAN and ISAC hardware acceleration can convert 2026 standards window into specification influence and customer lock-in for 2028-2030 deployment cycle
29. Platform licensing + service revenue sharing emerging as SoC business model evolution path, beyond chip sales, driven by MNO API/platform monetisation requirements
30. Pure volume growth strategy failing amid demand softness: AI performance leadership required to establish pricing power and avoid commoditisation in mobile SoC market

---

## ✅ Confirmed Facts (appeared in 2+ runs)

- MediaTek is executing a broad multi-front competitive challenge against Qualcomm and Broadcom spanning mobile SoC, Wi-Fi, and CPE/telecom markets
- CPE SoC competitive differentiation is shifting from hardware specs (bandwidth) toward software ecosystem integration and edge AI capability
- 6G commercial deployment is targeted for 2029-2030 with 3GPP Release 21 specification work to be formally scoped in June 2026
- On-device AI agent execution (multi-step autonomous workflows) is becoming a primary SoC capability benchmark replacing simple inference benchmarks
- TSMC advanced node demand is under pressure from Chinese OEM order reductions, affecting both Qualcomm and MediaTek production planning

---

## ⚠️ Information Gaps (not yet covered)

- [ ] Apple A19 / M-series AI SoC roadmap signals (iPhone 17 NPU specs, on-device AI feature pipeline) — query failed this run
- [ ] Samsung Exynos 2600 AI NPU detailed specs and competitive positioning vs. Snapdragon 8 Elite / Dimensity 9400
- [ ] Chinese OEM AI feature differentiation: Xiaomi HyperAI, OPPO AndesGPT, vivo BlueLM, Huawei Kirin AI agent capabilities
- [ ] Huawei HiSilicon Kirin AI SoC roadmap and 6G modem strategy under US sanctions constraints
- [ ] Killer app / super app AI agent monetisation models and SoC hardware dependency (WeChat, Grab, Gojek, etc.)
- [ ] On-device privacy regulations (EU AI Act, China PIPL, US state laws) specific impact on NPU/secure enclave SoC design requirements
- [ ] Qualcomm CPE-specific AI SoC roadmap (X Elite / X Plus in CPE context, Networking Pro series AI features)
- [ ] MediaTek Dimensity 9400+ / next-gen mobile SoC AI NPU benchmark data and architecture details
- [ ] Network operator-specific SoC procurement requirements (T-Mobile, SKT, KDDI, Rakuten) for AI-native RAN and CPE
- [ ] AI-RAN SoC architecture specifics: how Qualcomm, MediaTek, and Intel plan to address AI-RAN hardware acceleration in silicon
- [ ] ISAC (Integrated Sensing and Communications) hardware acceleration roadmap across SoC vendors for 6G
- [ ] In-package memory (HBM/LPDDR5X+) integration roadmap by SoC vendor for mobile and CPE use cases
- [ ] Android Bench LLM leaderboard detailed results and which SoC platforms score highest
- [ ] Wi-Fi 8 (IEEE 802.11bn) standardisation timeline and SoC vendor readiness beyond MediaTek/Broadcom
- [ ] Broadcom's AI/NPU strategy response to MediaTek CPE challenge beyond BCM6714/BCM6719

---

## 🔄 Repeated / High-Confidence Signals

- MediaTek challenging Qualcomm and Broadcom on multiple fronts simultaneously — appeared in both prior context and confirmed by Digitimes Apr 2026
- CPE market shifting from bandwidth to AI capability as primary operator procurement criterion — consistent signal across MediaTek MWC announcements and operator reports
- 6G commercial deployment window 2029-2030 with 3GPP as primary standards body — consistent across multiple 6G-related sources
- TSMC advanced node wafer loading decline of 10-15% due to demand softness and Chinese OEM cuts — confirmed across multiple Digitimes reports
- On-device AI agent as the new SoC capability benchmark — reinforced by Google Gemma 4, Android Agent Skills, and Android Bench leaderboard introduction

---

## 🎯 Next Search Priorities

> The next search run will focus on these topics first.

1. Samsung Exynos 2600 AI NPU strategy and specs — high competitive intelligence value, two consecutive runs with no data
2. Apple A19 / M-series AI SoC roadmap — critical for understanding premium segment AI benchmarking and competitive pressure on Android SoC vendors
3. Chinese OEM AI agent feature differentiation (Xiaomi HyperAI, OPPO AndesGPT, Huawei Kirin) — demand-side signal directly affecting MediaTek and Qualcomm order volumes
4. AI-RAN and ISAC SoC hardware acceleration roadmaps (Qualcomm, MediaTek, Intel) — critical for 6G standards window positioning identified as top strategic opportunity
5. Killer app / super app AI agent monetisation and SoC hardware dependency — needed to validate end-user demand pull for higher NPU specs in 2026-2027 flagship devices
