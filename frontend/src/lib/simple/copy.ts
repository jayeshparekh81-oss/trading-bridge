/**
 * Simple-mode words — every label a Level 1–3 customer can see, in four
 * languages. Hinglish first (the product's voice), then हिन्दी, ગુજરાતી, English.
 *
 * RULES (C3, founder 2026-09-05): no jargon. A 12-year-old must understand every
 * word. deploy / lots / NRML / webhook / execution mode / paper mode / kill
 * switch never appear here — they are "chalu karo", "kitna", "seekhne wala
 * mode", "Sab band". Keep each string short enough for a 375px tile.
 *
 * Keyed by the app's existing language switch (`useLanguage().lang`):
 * "hinglish" | "hi" | "gu" | "en". `t(lang, key)` never throws — a missing
 * language falls back to Hinglish, so no tile can ever render blank.
 */

import type { Lang } from "@/contexts/LanguageContext";

export type SimpleCopyKey =
  // levels
  | "level1_name"
  | "level2_name"
  | "level3_name"
  | "level4_name"
  // home
  | "home_greeting"
  | "home_subtitle"
  // tiles
  | "tile_strategy"
  | "tile_strategy_sub"
  | "tile_broker"
  | "tile_broker_sub"
  | "tile_signals"
  | "tile_signals_sub"
  | "tile_help"
  | "tile_help_sub"
  | "tile_templates"
  | "tile_templates_sub"
  | "tile_build"
  | "tile_build_sub"
  // status strip
  | "status_broker"
  | "status_broker_yes"
  | "status_broker_no"
  | "status_strategy"
  | "status_strategy_yes"
  | "status_strategy_no"
  | "status_signals"
  | "status_signals_none"
  | "status_learning_mode"
  // safety bar
  | "safety_pause"
  | "safety_pause_hint"
  | "safety_stop_all"
  | "safety_stop_all_hint"
  | "safety_settings"
  | "safety_logout"
  | "safety_confirm_pause"
  | "safety_confirm_stop_all"
  | "safety_yes"
  | "safety_no"
  | "safety_paused_done"
  | "safety_stopped_done"
  | "safety_nothing_running"
  // lesson of the day
  | "lesson_title"
  | "lesson_more"
  // hero / signal landing
  | "signal_landed"
  | "signal_none_today"
  | "signal_see_all"
  | "side_buy"
  | "side_sell"
  | "signal_exit"
  | "lang_title"
  | "nudge_prefix"
  // AlgoMitra nudges
  | "nudge_pro_sidebar"
  | "req_broker"
  | "req_subscribe"
  | "req_signal"
  | "req_template"
  | "req_backtest"
  | "req_build"
  | "tile_pro"
  | "progress_line"
  | "progress_next"
  | "pro_card_title"
  | "pro_card_body"
  | "ob_levels_note"
  | "nudge_home_first"
  | "shell_back"
  | "learn_section_title"
  | "learn_section_hint"
  | "tile_pro_sub"
  | "tip_templates"
  | "tip_build"
  | "tip_pro"
  // settings toggle
  | "settings_mode_title"
  | "settings_mode_simple"
  | "settings_mode_pro"
  | "settings_mode_help"
  | "settings_mode_saved"
  // simple onboarding
  | "ob_step_lang"
  | "ob_step_lang_body"
  | "ob_step_broker"
  | "ob_step_broker_body"
  | "ob_step_strategy"
  | "ob_step_strategy_body"
  | "ob_next"
  | "ob_skip"
  | "ob_done"
  | "ob_later";

type Dict = Record<SimpleCopyKey, string>;

const hinglish: Dict = {
  side_buy: "Kharida",
  side_sell: "Becha",
  signal_exit: "Nikal gaye",
  lang_title: "Bhasha",
  nudge_prefix: "AlgoMitra",
  level1_name: "Naya",
  level2_name: "Seekh raha",
  level3_name: "Banane wala",
  level4_name: "Pro",

  home_greeting: "Namaste, {name}",
  home_subtitle: "Char kaam. Bas itna hi.",

  tile_strategy: "Strategy chuno",
  tile_strategy_sub: "Taiyar strategy — dekho aur jodo",
  tile_broker: "Broker jodo",
  tile_broker_sub: "Apna Dhan account jodo",
  tile_signals: "Aaj ke signals",
  tile_signals_sub: "Aaj kya hua, ek jagah",
  tile_help: "Madad",
  tile_help_sub: "AlgoMitra se poocho ya WhatsApp karo",
  tile_templates: "Templates dekho",
  tile_templates_sub: "Taiyar strategies — ek click mein apni banao",
  tile_build: "Apni strategy banao",
  tile_build_sub: "Step by step, koi code nahi",

  status_broker: "Broker",
  status_broker_yes: "Juda hai",
  status_broker_no: "Abhi nahi juda",
  status_strategy: "Strategy",
  status_strategy_yes: "Chalu hai",
  status_strategy_no: "Abhi band hai",
  status_signals: "Aaj ke signals",
  status_signals_none: "Aaj koi nahi",
  status_learning_mode: "Seekhne wala mode — asli paisa nahi",

  safety_pause: "Rok do",
  safety_pause_hint: "Strategy ko abhi rok do — naye signal nahi aayenge",
  safety_stop_all: "Sab band",
  safety_stop_all_hint: "Sab kuch band — jo khula hai woh bhi band",
  safety_settings: "Settings",
  safety_logout: "Bahar",
  safety_confirm_pause: "Strategy rok dein? Jo khula hai woh waise hi rahega.",
  safety_confirm_stop_all: "Sab band karein? Jo khula hai woh sab band ho jayega. Yeh wapas nahi hota.",
  safety_yes: "Haan",
  safety_no: "Nahi",
  safety_paused_done: "Rok diya. Naye signal nahi aayenge.",
  safety_stopped_done: "Sab band ho gaya.",
  safety_nothing_running: "Abhi kuch chalu nahi hai.",

  lesson_title: "Aaj ka sabak",
  lesson_more: "Poora padho",

  signal_landed: "Naya signal aaya",
  signal_none_today: "Aaj abhi tak koi signal nahi. Bazaar khulne par yahin dikhega.",
  signal_see_all: "Sab signals dekho",

  nudge_pro_sidebar: "Yeh aapka poora menu hai — upar-baayein icon se chhupa/khol sakte ho",
  req_broker: "Broker jodo",
  req_subscribe: "Strategy chuno",
  req_signal: "pehla signal dekho",
  req_template: "Ek template try karo",
  req_backtest: "ek baar test chalao",
  req_build: "Apni strategy banao",
  tile_pro: "Pro mode (poora menu)",
  progress_line: "Aapka safar: {done} / {total} kadam",
  progress_next: "Agla: {step}",
  pro_card_title: "Sab kuch dekhna hai? Pro mode kholo →",
  pro_card_body: "Poora menu: charts, builders, analytics — pehle se jaante ho toh yahan.",
  ob_levels_note: "Ghar pe pehle char kaam upar hain — wahin se shuru karo. Jab chaho, Pro mode se sab dekh sakte ho.",
  nudge_home_first: "Yeh aapka ghar hai — char kaam upar, baaki neeche. Pro mode se kabhi bhi sab dekh sakte ho.",
  shell_back: "Wapas",
  learn_section_title: "Aur seekhein",
  learn_section_hint: "Pehle upar wale 4 karo, phir yeh — aaram se.",
  tile_pro_sub: "Poora menu — charts, builders, analytics",
  tip_templates: "Templates = taiyar strategies. Ek chuno, ek click mein apni banao.",
  tip_build: "Yahan aap apni strategy khud banate ho — 5 aasan kadam, test apne aap.",
  tip_pro: "Pro mode = poora menu. Kabhi bhi Settings se wapas Aasan pe aa sakte ho.",

  settings_mode_title: "Aapka mode",
  settings_mode_simple: "Aasan",
  settings_mode_pro: "Pro",
  settings_mode_help: "Aasan = kam cheezein, badi. Pro = poora menu. Kabhi bhi badlo — kuch nahi khota.",
  settings_mode_saved: "Mode badal gaya",

  ob_step_lang: "Bhasha chuno",
  ob_step_lang_body: "Jis bhasha mein aaram ho, woh chuno. Kabhi bhi badal sakte ho.",
  ob_step_broker: "Broker jodo",
  ob_step_broker_body: "Aapka paisa aapke broker ke paas hi rehta hai. Hum sirf signal bhejte hain.",
  ob_step_strategy: "Strategy chuno",
  ob_step_strategy_body: "Ek taiyar strategy dekho. Pasand aaye to jodo — nahi to baad mein.",
  ob_next: "Aage",
  ob_skip: "Baad mein karunga",
  ob_done: "Shuru karo",
  ob_later: "Abhi nahi",
};

const hi: Dict = {
  side_buy: "खरीदा",
  side_sell: "बेचा",
  signal_exit: "निकल गए",
  lang_title: "भाषा",
  nudge_prefix: "AlgoMitra",
  level1_name: "नया",
  level2_name: "सीख रहा",
  level3_name: "बनाने वाला",
  level4_name: "प्रो",

  home_greeting: "नमस्ते, {name}",
  home_subtitle: "चार काम। बस इतना ही।",

  tile_strategy: "स्ट्रैटेजी चुनो",
  tile_strategy_sub: "तैयार स्ट्रैटेजी — देखो और जोड़ो",
  tile_broker: "ब्रोकर जोड़ो",
  tile_broker_sub: "अपना Dhan खाता जोड़ो",
  tile_signals: "आज के सिग्नल",
  tile_signals_sub: "आज क्या हुआ, एक जगह",
  tile_help: "मदद",
  tile_help_sub: "AlgoMitra से पूछो या WhatsApp करो",
  tile_templates: "टेम्पलेट देखो",
  tile_templates_sub: "तैयार स्ट्रैटेजी — एक क्लिक में अपनी बनाओ",
  tile_build: "अपनी स्ट्रैटेजी बनाओ",
  tile_build_sub: "कदम-दर-कदम, कोई कोड नहीं",

  status_broker: "ब्रोकर",
  status_broker_yes: "जुड़ा है",
  status_broker_no: "अभी नहीं जुड़ा",
  status_strategy: "स्ट्रैटेजी",
  status_strategy_yes: "चालू है",
  status_strategy_no: "अभी बंद है",
  status_signals: "आज के सिग्नल",
  status_signals_none: "आज कोई नहीं",
  status_learning_mode: "सीखने वाला मोड — असली पैसा नहीं",

  safety_pause: "रोक दो",
  safety_pause_hint: "स्ट्रैटेजी अभी रोक दो — नए सिग्नल नहीं आएंगे",
  safety_stop_all: "सब बंद",
  safety_stop_all_hint: "सब कुछ बंद — जो खुला है वह भी बंद",
  safety_settings: "सेटिंग्स",
  safety_logout: "बाहर",
  safety_confirm_pause: "स्ट्रैटेजी रोक दें? जो खुला है वह वैसे ही रहेगा।",
  safety_confirm_stop_all: "सब बंद करें? जो खुला है वह सब बंद हो जाएगा। यह वापस नहीं होता।",
  safety_yes: "हाँ",
  safety_no: "नहीं",
  safety_paused_done: "रोक दिया। नए सिग्नल नहीं आएंगे।",
  safety_stopped_done: "सब बंद हो गया।",
  safety_nothing_running: "अभी कुछ चालू नहीं है।",

  lesson_title: "आज का सबक",
  lesson_more: "पूरा पढ़ो",

  signal_landed: "नया सिग्नल आया",
  signal_none_today: "आज अभी तक कोई सिग्नल नहीं। बाज़ार खुलने पर यहीं दिखेगा।",
  signal_see_all: "सब सिग्नल देखो",

  nudge_pro_sidebar: "यह आपका पूरा मेन्यू है — ऊपर-बाएँ आइकन से छुपा/खोल सकते हो",
  req_broker: "ब्रोकर जोड़ो",
  req_subscribe: "स्ट्रैटेजी चुनो",
  req_signal: "पहला सिग्नल देखो",
  req_template: "एक टेम्पलेट आज़माओ",
  req_backtest: "एक बार टेस्ट चलाओ",
  req_build: "अपनी स्ट्रैटेजी बनाओ",
  tile_pro: "प्रो मोड (पूरा मेन्यू)",
  progress_line: "आपका सफ़र: {done} / {total} कदम",
  progress_next: "अगला: {step}",
  pro_card_title: "सब कुछ देखना है? प्रो मोड खोलो →",
  pro_card_body: "पूरा मेन्यू: चार्ट, बिल्डर, एनालिटिक्स — पहले से जानते हो तो यहाँ।",
  ob_levels_note: "घर पर पहले चार काम ऊपर हैं — वहीं से शुरू करो। जब चाहो, प्रो मोड से सब देख सकते हो।",
  nudge_home_first: "यह आपका घर है — चार काम ऊपर, बाकी नीचे। प्रो मोड से कभी भी सब देख सकते हो।",
  shell_back: "वापस",
  learn_section_title: "और सीखें",
  learn_section_hint: "पहले ऊपर वाले 4 करो, फिर यह — आराम से।",
  tile_pro_sub: "पूरा मेन्यू — चार्ट, बिल्डर, एनालिटिक्स",
  tip_templates: "टेम्पलेट = तैयार स्ट्रैटेजी। एक चुनो, एक क्लिक में अपनी बनाओ।",
  tip_build: "यहाँ आप अपनी स्ट्रैटेजी खुद बनाते हैं — 5 आसान कदम, टेस्ट अपने आप।",
  tip_pro: "प्रो मोड = पूरा मेन्यू। कभी भी सेटिंग्स से वापस आसान पर आ सकते हो।",

  settings_mode_title: "आपका मोड",
  settings_mode_simple: "आसान",
  settings_mode_pro: "प्रो",
  settings_mode_help: "आसान = कम चीज़ें, बड़ी। प्रो = पूरा मेन्यू। कभी भी बदलो — कुछ नहीं खोता।",
  settings_mode_saved: "मोड बदल गया",

  ob_step_lang: "भाषा चुनो",
  ob_step_lang_body: "जिस भाषा में आराम हो, वह चुनो। कभी भी बदल सकते हो।",
  ob_step_broker: "ब्रोकर जोड़ो",
  ob_step_broker_body: "आपका पैसा आपके ब्रोकर के पास ही रहता है। हम सिर्फ़ सिग्नल भेजते हैं।",
  ob_step_strategy: "स्ट्रैटेजी चुनो",
  ob_step_strategy_body: "एक तैयार स्ट्रैटेजी देखो। पसंद आए तो जोड़ो — नहीं तो बाद में।",
  ob_next: "आगे",
  ob_skip: "बाद में करूँगा",
  ob_done: "शुरू करो",
  ob_later: "अभी नहीं",
};

const gu: Dict = {
  side_buy: "ખરીદ્યું",
  side_sell: "વેચ્યું",
  signal_exit: "નીકળી ગયા",
  lang_title: "ભાષા",
  nudge_prefix: "AlgoMitra",
  level1_name: "નવો",
  level2_name: "શીખી રહ્યો",
  level3_name: "બનાવનાર",
  level4_name: "પ્રો",

  home_greeting: "નમસ્તે, {name}",
  home_subtitle: "ચાર કામ. બસ આટલું જ.",

  tile_strategy: "સ્ટ્રેટેજી પસંદ કરો",
  tile_strategy_sub: "તૈયાર સ્ટ્રેટેજી — જુઓ અને જોડો",
  tile_broker: "બ્રોકર જોડો",
  tile_broker_sub: "તમારું Dhan ખાતું જોડો",
  tile_signals: "આજના સિગ્નલ",
  tile_signals_sub: "આજે શું થયું, એક જગ્યાએ",
  tile_help: "મદદ",
  tile_help_sub: "AlgoMitra ને પૂછો કે WhatsApp કરો",
  tile_templates: "ટેમ્પલેટ જુઓ",
  tile_templates_sub: "તૈયાર સ્ટ્રેટેજી — એક ક્લિકમાં તમારી બનાવો",
  tile_build: "તમારી સ્ટ્રેટેજી બનાવો",
  tile_build_sub: "પગલે-પગલે, કોઈ કોડ નહીં",

  status_broker: "બ્રોકર",
  status_broker_yes: "જોડાયેલ છે",
  status_broker_no: "હજુ જોડાયું નથી",
  status_strategy: "સ્ટ્રેટેજી",
  status_strategy_yes: "ચાલુ છે",
  status_strategy_no: "હમણાં બંધ છે",
  status_signals: "આજના સિગ્નલ",
  status_signals_none: "આજે કોઈ નહીં",
  status_learning_mode: "શીખવાનો મોડ — સાચા પૈસા નહીં",

  safety_pause: "રોકો",
  safety_pause_hint: "સ્ટ્રેટેજી હમણાં રોકો — નવા સિગ્નલ નહીં આવે",
  safety_stop_all: "બધું બંધ",
  safety_stop_all_hint: "બધું બંધ — જે ખુલ્લું છે તે પણ બંધ",
  safety_settings: "સેટિંગ્સ",
  safety_logout: "બહાર",
  safety_confirm_pause: "સ્ટ્રેટેજી રોકવી છે? જે ખુલ્લું છે તે એમ જ રહેશે.",
  safety_confirm_stop_all: "બધું બંધ કરવું છે? જે ખુલ્લું છે તે બધું બંધ થઈ જશે. આ પાછું નથી થતું.",
  safety_yes: "હા",
  safety_no: "ના",
  safety_paused_done: "રોકી દીધું. નવા સિગ્નલ નહીં આવે.",
  safety_stopped_done: "બધું બંધ થઈ ગયું.",
  safety_nothing_running: "હમણાં કંઈ ચાલુ નથી.",

  lesson_title: "આજનો પાઠ",
  lesson_more: "પૂરું વાંચો",

  signal_landed: "નવો સિગ્નલ આવ્યો",
  signal_none_today: "આજે હજુ સુધી કોઈ સિગ્નલ નથી. બજાર ખુલશે ત્યારે અહીં જ દેખાશે.",
  signal_see_all: "બધા સિગ્નલ જુઓ",

  nudge_pro_sidebar: "આ તમારું પૂરું મેનુ છે — ઉપર-ડાબે આઇકનથી છુપાવી/ખોલી શકો છો",
  req_broker: "બ્રોકર જોડો",
  req_subscribe: "સ્ટ્રેટેજી પસંદ કરો",
  req_signal: "પહેલો સિગ્નલ જુઓ",
  req_template: "એક ટેમ્પલેટ અજમાવો",
  req_backtest: "એક વાર ટેસ્ટ ચલાવો",
  req_build: "તમારી સ્ટ્રેટેજી બનાવો",
  tile_pro: "પ્રો મોડ (પૂરું મેનુ)",
  progress_line: "તમારી સફર: {done} / {total} પગલાં",
  progress_next: "આગળ: {step}",
  pro_card_title: "બધું જોવું છે? પ્રો મોડ ખોલો →",
  pro_card_body: "પૂરું મેનુ: ચાર્ટ, બિલ્ડર, એનાલિટિક્સ — પહેલેથી જાણો છો તો અહીં.",
  ob_levels_note: "ઘર પર પહેલા ચાર કામ ઉપર છે — ત્યાંથી શરૂ કરો. જ્યારે ઈચ્છો, પ્રો મોડથી બધું જોઈ શકો છો.",
  nudge_home_first: "આ તમારું ઘર છે — ચાર કામ ઉપર, બાકી નીચે. પ્રો મોડથી ગમે ત્યારે બધું જોઈ શકો છો.",
  shell_back: "પાછા",
  learn_section_title: "વધુ શીખો",
  learn_section_hint: "પહેલા ઉપરના 4 કરો, પછી આ — આરામથી.",
  tile_pro_sub: "પૂરું મેનુ — ચાર્ટ, બિલ્ડર, એનાલિટિક્સ",
  tip_templates: "ટેમ્પલેટ = તૈયાર સ્ટ્રેટેજી. એક પસંદ કરો, એક ક્લિકમાં તમારી બનાવો.",
  tip_build: "અહીં તમે તમારી સ્ટ્રેટેજી જાતે બનાવો છો — 5 સરળ પગલાં, ટેસ્ટ આપોઆપ.",
  tip_pro: "પ્રો મોડ = પૂરું મેનુ. ગમે ત્યારે સેટિંગ્સથી પાછા સરળ પર આવી શકો છો.",

  settings_mode_title: "તમારો મોડ",
  settings_mode_simple: "સરળ",
  settings_mode_pro: "પ્રો",
  settings_mode_help: "સરળ = ઓછી વસ્તુઓ, મોટી. પ્રો = પૂરું મેનુ. ગમે ત્યારે બદલો — કંઈ ખોવાતું નથી.",
  settings_mode_saved: "મોડ બદલાઈ ગયો",

  ob_step_lang: "ભાષા પસંદ કરો",
  ob_step_lang_body: "જે ભાષામાં આરામ હોય તે પસંદ કરો. ગમે ત્યારે બદલી શકો છો.",
  ob_step_broker: "બ્રોકર જોડો",
  ob_step_broker_body: "તમારા પૈસા તમારા બ્રોકર પાસે જ રહે છે. અમે ફક્ત સિગ્નલ મોકલીએ છીએ.",
  ob_step_strategy: "સ્ટ્રેટેજી પસંદ કરો",
  ob_step_strategy_body: "એક તૈયાર સ્ટ્રેટેજી જુઓ. ગમે તો જોડો — નહીં તો પછી.",
  ob_next: "આગળ",
  ob_skip: "પછી કરીશ",
  ob_done: "શરૂ કરો",
  ob_later: "હમણાં નહીં",
};

const en: Dict = {
  side_buy: "Bought",
  side_sell: "Sold",
  signal_exit: "Exited",
  lang_title: "Language",
  nudge_prefix: "AlgoMitra",
  level1_name: "New",
  level2_name: "Learning",
  level3_name: "Builder",
  level4_name: "Pro",

  home_greeting: "Hello, {name}",
  home_subtitle: "Four things. That is all.",

  tile_strategy: "Pick a strategy",
  tile_strategy_sub: "A ready strategy — see it and join it",
  tile_broker: "Connect broker",
  tile_broker_sub: "Connect your Dhan account",
  tile_signals: "Today's signals",
  tile_signals_sub: "What happened today, in one place",
  tile_help: "Help",
  tile_help_sub: "Ask AlgoMitra or message on WhatsApp",
  tile_templates: "See templates",
  tile_templates_sub: "Ready strategies — make one yours in a click",
  tile_build: "Build your strategy",
  tile_build_sub: "Step by step, no code",

  status_broker: "Broker",
  status_broker_yes: "Connected",
  status_broker_no: "Not connected yet",
  status_strategy: "Strategy",
  status_strategy_yes: "Running",
  status_strategy_no: "Off for now",
  status_signals: "Today's signals",
  status_signals_none: "None today",
  status_learning_mode: "Learning mode — no real money",

  safety_pause: "Pause",
  safety_pause_hint: "Pause the strategy now — no new signals",
  safety_stop_all: "Stop all",
  safety_stop_all_hint: "Stop everything — anything open is closed too",
  safety_settings: "Settings",
  safety_logout: "Log out",
  safety_confirm_pause: "Pause the strategy? Anything open stays as it is.",
  safety_confirm_stop_all: "Stop everything? Anything open will be closed. This cannot be undone.",
  safety_yes: "Yes",
  safety_no: "No",
  safety_paused_done: "Paused. No new signals will come.",
  safety_stopped_done: "Everything is stopped.",
  safety_nothing_running: "Nothing is running right now.",

  lesson_title: "Today's lesson",
  lesson_more: "Read more",

  signal_landed: "A new signal arrived",
  signal_none_today: "No signal yet today. It will show here when the market opens.",
  signal_see_all: "See all signals",

  nudge_pro_sidebar: "This is your full menu — hide or show it with the icon at the top left",
  req_broker: "Connect a broker",
  req_subscribe: "Pick a strategy",
  req_signal: "see your first signal",
  req_template: "Try one template",
  req_backtest: "run one test",
  req_build: "Build your own strategy",
  tile_pro: "Pro mode (full menu)",
  progress_line: "Your journey: step {done} of {total}",
  progress_next: "Next: {step}",
  pro_card_title: "Want to see everything? Open Pro mode →",
  pro_card_body: "The full menu: charts, builders, analytics — if you already know your way, it is here.",
  ob_levels_note: "On the home the first four things are at the top — start there. Whenever you like, Pro mode shows everything.",
  nudge_home_first: "This is your home — four things at the top, the rest below. Pro mode shows everything any time.",
  shell_back: "Back",
  learn_section_title: "Learn more",
  learn_section_hint: "Do the four above first, then these — at your own pace.",
  tile_pro_sub: "The full menu — charts, builders, analytics",
  tip_templates: "Templates are ready-made strategies. Pick one and make it yours in a click.",
  tip_build: "Here you build your own strategy — five easy steps, the test runs by itself.",
  tip_pro: "Pro mode is the full menu. You can come back to Simple from Settings any time.",

  settings_mode_title: "Your mode",
  settings_mode_simple: "Simple",
  settings_mode_pro: "Pro",
  settings_mode_help: "Simple = fewer things, bigger. Pro = the full menu. Switch any time — nothing is lost.",
  settings_mode_saved: "Mode changed",

  ob_step_lang: "Pick a language",
  ob_step_lang_body: "Pick the language you are comfortable in. You can change it any time.",
  ob_step_broker: "Connect broker",
  ob_step_broker_body: "Your money stays with your broker. We only send the signals.",
  ob_step_strategy: "Pick a strategy",
  ob_step_strategy_body: "Look at one ready strategy. Join it if you like it — or later.",
  ob_next: "Next",
  ob_skip: "I'll do it later",
  ob_done: "Start",
  ob_later: "Not now",
};

const DICTS: Record<Lang, Dict> = { hinglish, hi, gu, en };

/** Resolve a Simple-mode string; `{name}`-style tokens are filled from `vars`. */
export function t(lang: Lang, key: SimpleCopyKey, vars?: Record<string, string | number>): string {
  const dict = DICTS[lang] ?? hinglish;
  let s = dict[key] ?? hinglish[key] ?? key;
  if (vars) {
    for (const [k, v] of Object.entries(vars)) s = s.split(`{${k}}`).join(String(v));
  }
  return s;
}

/** Every string in every language — for the no-jargon lint test. */
export function allSimpleStrings(): Array<{ lang: Lang; key: SimpleCopyKey; text: string }> {
  const out: Array<{ lang: Lang; key: SimpleCopyKey; text: string }> = [];
  for (const lang of Object.keys(DICTS) as Lang[]) {
    for (const [key, text] of Object.entries(DICTS[lang]) as Array<[SimpleCopyKey, string]>) {
      out.push({ lang, key, text });
    }
  }
  return out;
}

/** Words that must never appear on a Level 1–3 surface (C3). */
export const JARGON_BLOCKLIST: readonly RegExp[] = [
  /\bdeploy/i,
  /\blots?\b/i,
  /\bNRML\b/,
  /\bMIS\b/,
  /\bwebhook/i,
  /execution mode/i,
  /\bpaper\s*mode/i,
  /\bpaper\b/i,
  /kill\s*switch/i,
  /\bHMAC\b/,
  /\bJSON\b/,
  /\bAPI\b/,
  /\bslippage/i,
  /\bP&L\b/,
  /\bPnL\b/i,
  /\bbacktest/i,
];
