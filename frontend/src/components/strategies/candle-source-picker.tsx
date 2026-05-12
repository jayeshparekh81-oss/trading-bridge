"use client";

import { useId, useMemo } from "react";
import { CandlestickChart, Database, Sparkles } from "lucide-react";
import { GlassmorphismCard } from "@/components/ui/glassmorphism-card";
import { Badge } from "@/components/ui/badge";
import { Autocomplete } from "@/components/ui/autocomplete";
import { cn } from "@/lib/utils";

/**
 * Candle source picker — used by Phase 5 builders and the backtest
 * result page. State is controlled so callers persist it through
 * navigation (typically via ``localStorage`` between the builder and
 * the backtest result page).
 */

export type CandleSource = "synthetic" | "dhan_historical";
export type CandleTimeframe = "1m" | "5m" | "15m" | "1h" | "1d";

/** Wire shape expected by ``POST /strategies/{id}/backtest`` body. */
export interface CandlesRequestPayload {
  symbol: string;
  timeframe: CandleTimeframe;
  from_date: string; // ISO 8601 UTC
  to_date: string; // ISO 8601 UTC
}

export interface CandleSourcePickerValue {
  source: CandleSource;
  /** Filled only when ``source === "dhan_historical"``. */
  candles_request: CandlesRequestPayload | null;
  /** Local validation error (e.g., from > to). Empty string when ok. */
  validation_error: string;
}

interface Props {
  value: CandleSourcePickerValue;
  onChange: (value: CandleSourcePickerValue) => void;
  /** When ``true`` the picker hides the "Synthetic" toggle and shows
   * only the Dhan form. The beginner builder skips the picker entirely
   * — this prop is for the backtest page where the user has already
   * opted into a real-data re-run. */
  forceDhan?: boolean;
  /** When ``true``, render a compact hint that the symbol list is
   * the bundled subset (used inside dialogs to keep the chrome
   * minimal). */
  compactHint?: boolean;
}

/** Hard-coded sample of the symbols the Phase B adapter resolves
 *  server-side. Future: ``GET /api/data-provider/symbols``.
 *
 *  Shape: ``{ label, symbol }`` so the datalist can show a friendly
 *  display label ("Nifty Next 50", "Reliance Industries") while
 *  emitting the canonical Dhan trading symbol ("NIFTY NEXT 50",
 *  "RELIANCE") to the backtest request.
 *
 *  Step 1/5 v2 — coordinated with backend ``KNOWN_SYMBOLS`` in
 *  ``backend/app/strategy_engine/data_provider/constants.py``. Every
 *  ``symbol`` value below must have a matching entry there (or an
 *  alias) or the backend's ``_resolve_symbol`` raises ValueError →
 *  uncaught 500.
 *
 *  Backward-compat invariant — NON-NEGOTIABLE: all ten pre-existing
 *  symbol strings remain byte-identical so previously-saved strategies
 *  resolve unchanged:
 *    NIFTY, BANKNIFTY, FINNIFTY,
 *    RELIANCE, TCS, INFY, HDFCBANK, ICICIBANK, AXISBANK, ITC.
 *
 *  Three logical groups: F&O NSE indices, F&O BSE indices, large-cap
 *  cash equities. Broader equity expansion is queued for Steps 3-5.
 *  Sectoral / spot-only indices (Nifty IT, Auto, Pharma, etc.) are
 *  intentionally excluded — they have no F&O contracts on either
 *  exchange and live data is not yet wired for them.
 */
export const KNOWN_SYMBOLS: ReadonlyArray<{ label: string; symbol: string }> = [
  // ── F&O indices (7) ─ NSE: NIFTY/BANKNIFTY/FINNIFTY/MIDCPNIFTY,
  //    BSE: SENSEX/BANKEX/SNSX50. Nifty Next 50 (sec_id 38) is
  //    intentionally absent — Dhan rejects the historical-data
  //    triple with HTTP 400; see ``docs/POST_LAUNCH_TECH_DEBT.md``.
  { label: "Nifty 50", symbol: "NIFTY" },
  { label: "Bank Nifty", symbol: "BANKNIFTY" },
  { label: "Fin Nifty", symbol: "FINNIFTY" },
  { label: "Nifty Midcap Select", symbol: "MIDCPNIFTY" },
  { label: "Sensex", symbol: "SENSEX" },
  { label: "Bankex", symbol: "BANKEX" },
  { label: "Sensex 50", symbol: "SNSX50" },
  // ── F&O stocks (209, alphabetical) — Step 3. The 7 historical
  //    large-caps preserve their existing display labels (RELIANCE
  //    → "Reliance Industries" etc.); the remaining 202 default to
  //    label=symbol. Regenerated from Dhan scrip-master — see
  //    ``backend/.../constants.py`` docblock for the filter and
  //    regeneration command, kept in lockstep with backend
  //    ``KNOWN_SYMBOLS``.
  { label: "360 One WAM", symbol: "360ONE" },
  { label: "ABB", symbol: "ABB" },
  { label: "Aditya Birla Capital", symbol: "ABCAPITAL" },
  { label: "Adani Energy Solutions", symbol: "ADANIENSOL" },
  { label: "Adani Enterprises", symbol: "ADANIENT" },
  { label: "Adani Green Energy", symbol: "ADANIGREEN" },
  { label: "Adani Ports & SEZ", symbol: "ADANIPORTS" },
  { label: "Adani Power", symbol: "ADANIPOWER" },
  { label: "Alkem Laboratories", symbol: "ALKEM" },
  { label: "Amber Enterprises", symbol: "AMBER" },
  { label: "Ambuja Cements", symbol: "AMBUJACEM" },
  { label: "Angel One", symbol: "ANGELONE" },
  { label: "APL Apollo Tubes", symbol: "APLAPOLLO" },
  { label: "Apollo Hospitals", symbol: "APOLLOHOSP" },
  { label: "Ashok Leyland", symbol: "ASHOKLEY" },
  { label: "Asian Paints", symbol: "ASIANPAINT" },
  { label: "Astral", symbol: "ASTRAL" },
  { label: "AU Small Finance Bank", symbol: "AUBANK" },
  { label: "Aurobindo Pharma", symbol: "AUROPHARMA" },
  { label: "Axis Bank", symbol: "AXISBANK" },
  { label: "Bajaj Auto", symbol: "BAJAJ-AUTO" },
  { label: "Bajaj Finserv", symbol: "BAJAJFINSV" },
  { label: "Bajaj Holdings & Investments", symbol: "BAJAJHLDNG" },
  { label: "Bajaj Finance", symbol: "BAJFINANCE" },
  { label: "Bandhan Bank", symbol: "BANDHANBNK" },
  { label: "Bank of Baroda", symbol: "BANKBARODA" },
  { label: "Bank of India", symbol: "BANKINDIA" },
  { label: "Bharat Dynamics", symbol: "BDL" },
  { label: "Bharat Electronics", symbol: "BEL" },
  { label: "Bharat Forge", symbol: "BHARATFORG" },
  { label: "Bharti Airtel", symbol: "BHARTIARTL" },
  { label: "Bharat Heavy Electricals", symbol: "BHEL" },
  { label: "Biocon", symbol: "BIOCON" },
  { label: "Blue Star", symbol: "BLUESTARCO" },
  { label: "Bosch", symbol: "BOSCHLTD" },
  { label: "Bharat Petroleum", symbol: "BPCL" },
  { label: "Britannia Industries", symbol: "BRITANNIA" },
  { label: "BSE", symbol: "BSE" },
  { label: "CAMS", symbol: "CAMS" },
  { label: "Canara Bank", symbol: "CANBK" },
  { label: "CDSL", symbol: "CDSL" },
  { label: "CG Power & Industrial Solutions", symbol: "CGPOWER" },
  { label: "CIFCL-7.5%-30092026-NCD", symbol: "CHOLAFIN" },
  { label: "Cipla", symbol: "CIPLA" },
  { label: "Coal India", symbol: "COALINDIA" },
  { label: "Cochin Shipyard", symbol: "COCHINSHIP" },
  { label: "Coforge", symbol: "COFORGE" },
  { label: "Colgate Palmolive", symbol: "COLPAL" },
  { label: "Container Corporation of India", symbol: "CONCOR" },
  { label: "Crompton Greaves", symbol: "CROMPTON" },
  { label: "Cummins", symbol: "CUMMINSIND" },
  { label: "Dabur India", symbol: "DABUR" },
  { label: "Dalmia Bharat", symbol: "DALBHARAT" },
  { label: "Delhivery", symbol: "DELHIVERY" },
  { label: "Divis Laboratories", symbol: "DIVISLAB" },
  { label: "Dixon Technologies", symbol: "DIXON" },
  { label: "DLF", symbol: "DLF" },
  { label: "Avenue Supermarts DMart", symbol: "DMART" },
  { label: "Dr Reddys Laboratories", symbol: "DRREDDY" },
  { label: "Eicher Motors", symbol: "EICHERMOT" },
  { label: "Eternal", symbol: "ETERNAL" },
  { label: "Exide Industries", symbol: "EXIDEIND" },
  { label: "Federal Bank", symbol: "FEDERALBNK" },
  { label: "Force Motors", symbol: "FORCEMOT" },
  { label: "Fortis Healthcare", symbol: "FORTIS" },
  { label: "GAIL", symbol: "GAIL" },
  { label: "Glenmark Pharmaceuticals", symbol: "GLENMARK" },
  { label: "GMR Airports", symbol: "GMRAIRPORT" },
  { label: "Godfrey Phillips", symbol: "GODFRYPHLP" },
  { label: "Godrej Consumer Products", symbol: "GODREJCP" },
  { label: "Godrej Properties", symbol: "GODREJPROP" },
  { label: "Grasim Industries", symbol: "GRASIM" },
  { label: "Hindustan Aeronautics", symbol: "HAL" },
  { label: "Havells", symbol: "HAVELLS" },
  { label: "HCL Technologies", symbol: "HCLTECH" },
  { label: "HDFC AMC", symbol: "HDFCAMC" },
  { label: "HDFC Bank", symbol: "HDFCBANK" },
  { label: "HDFC Life Insurance", symbol: "HDFCLIFE" },
  { label: "Hero Motocorp", symbol: "HEROMOTOCO" },
  { label: "Hindalco Industries", symbol: "HINDALCO" },
  { label: "Hindustan Petroleum", symbol: "HINDPETRO" },
  { label: "Hindustan Unilever", symbol: "HINDUNILVR" },
  { label: "Hindustan Zinc", symbol: "HINDZINC" },
  { label: "Hyundai Motor India", symbol: "HYUNDAI" },
  { label: "ICICI Bank", symbol: "ICICIBANK" },
  { label: "ICICI Lombard General Insurance", symbol: "ICICIGI" },
  { label: "ICICI Prudential Life Insurance", symbol: "ICICIPRULI" },
  { label: "Vodafone Idea", symbol: "IDEA" },
  { label: "IDFC First Bank", symbol: "IDFCFIRSTB" },
  { label: "Indian Energy Exchange", symbol: "IEX" },
  { label: "Indian Hotels Company", symbol: "INDHOTEL" },
  { label: "Indian Bank", symbol: "INDIANB" },
  { label: "Interglobe Aviation", symbol: "INDIGO" },
  { label: "Indusind Bank", symbol: "INDUSINDBK" },
  { label: "Indus Towers", symbol: "INDUSTOWER" },
  { label: "Infosys", symbol: "INFY" },
  { label: "Inox Wind", symbol: "INOXWIND" },
  { label: "Indian Oil Corporation", symbol: "IOC" },
  { label: "IREDA", symbol: "IREDA" },
  { label: "IRFC", symbol: "IRFC" },
  { label: "ITC", symbol: "ITC" },
  { label: "Jindal Steel", symbol: "JINDALSTEL" },
  { label: "Jio Financial Services", symbol: "JIOFIN" },
  { label: "JSW Energy", symbol: "JSWENERGY" },
  { label: "JSW Steel", symbol: "JSWSTEEL" },
  { label: "Jubilant FoodWorks", symbol: "JUBLFOOD" },
  { label: "Kalyan Jewellers", symbol: "KALYANKJIL" },
  { label: "Kaynes Technology India", symbol: "KAYNES" },
  { label: "KEI Industries", symbol: "KEI" },
  { label: "KFin Technologies", symbol: "KFINTECH" },
  { label: "Kotak Bank", symbol: "KOTAKBANK" },
  { label: "KPIT Technologies", symbol: "KPITTECH" },
  { label: "Laurus Labs", symbol: "LAURUSLABS" },
  { label: "LIC Housing Finance", symbol: "LICHSGFIN" },
  { label: "LIC of India", symbol: "LICI" },
  { label: "Lodha Developers", symbol: "LODHA" },
  { label: "Larsen & Toubro", symbol: "LT" },
  { label: "L&T Finance", symbol: "LTF" },
  { label: "LTM", symbol: "LTM" },
  { label: "Lupin", symbol: "LUPIN" },
  { label: "Mahindra & Mahindra", symbol: "M&M" },
  { label: "Manappuram Finance", symbol: "MANAPPURAM" },
  { label: "Mankind Pharma", symbol: "MANKIND" },
  { label: "Marico", symbol: "MARICO" },
  { label: "Maruti Suzuki", symbol: "MARUTI" },
  { label: "Max Healthcare Institute", symbol: "MAXHEALTH" },
  { label: "Mazagon Dock Shipbuilders", symbol: "MAZDOCK" },
  { label: "MCX", symbol: "MCX" },
  { label: "Max Financial Services", symbol: "MFSL" },
  { label: "SMIL-6.5%-20092027-NCD", symbol: "MOTHERSON" },
  { label: "Motilal Oswal Financial Services", symbol: "MOTILALOFS" },
  { label: "Mphasis", symbol: "MPHASIS" },
  { label: "Muthoot Finance", symbol: "MUTHOOTFIN" },
  { label: "Nippon Life India AMC", symbol: "NAM-INDIA" },
  { label: "NALCO", symbol: "NATIONALUM" },
  { label: "Info Edge", symbol: "NAUKRI" },
  { label: "NBCC", symbol: "NBCC" },
  { label: "Nestle", symbol: "NESTLEIND" },
  { label: "NHPC", symbol: "NHPC" },
  { label: "NMDC", symbol: "NMDC" },
  { label: "NTPC", symbol: "NTPC" },
  { label: "Nuvama Wealth Management", symbol: "NUVAMA" },
  { label: "Nykaa", symbol: "NYKAA" },
  { label: "Oberoi Realty", symbol: "OBEROIRLTY" },
  { label: "Oracle Financial Services Software", symbol: "OFSS" },
  { label: "Oil India", symbol: "OIL" },
  { label: "Oil & Natural Gas Corporation", symbol: "ONGC" },
  { label: "Page Industries", symbol: "PAGEIND" },
  { label: "Patanjali Foods", symbol: "PATANJALI" },
  { label: "One 97 Communications", symbol: "PAYTM" },
  { label: "Persistent Systems", symbol: "PERSISTENT" },
  { label: "Petronet LNG", symbol: "PETRONET" },
  { label: "Power Finance Corporation", symbol: "PFC" },
  { label: "PG Electroplast", symbol: "PGEL" },
  { label: "Phoenix Mills", symbol: "PHOENIXLTD" },
  { label: "Pidilite Industries", symbol: "PIDILITIND" },
  { label: "PI Industries", symbol: "PIIND" },
  { label: "Punjab National Bank", symbol: "PNB" },
  { label: "PNB Housing Finance", symbol: "PNBHOUSING" },
  { label: "PB FinTech", symbol: "POLICYBZR" },
  { label: "Polycab", symbol: "POLYCAB" },
  { label: "Power Grid Corporation of India", symbol: "POWERGRID" },
  { label: "Hitachi Energy", symbol: "POWERINDIA" },
  { label: "Premier Energies", symbol: "PREMIERENE" },
  { label: "Prestige Estates Projects", symbol: "PRESTIGE" },
  { label: "RBL Bank", symbol: "RBLBANK" },
  { label: "REC", symbol: "RECLTD" },
  { label: "Reliance Industries", symbol: "RELIANCE" },
  { label: "Rail Vikas Nigam", symbol: "RVNL" },
  { label: "Steel Authority of India", symbol: "SAIL" },
  { label: "Sammaan Capital", symbol: "SAMMAANCAP" },
  { label: "SBI Cards", symbol: "SBICARD" },
  { label: "SBI Life Insurance", symbol: "SBILIFE" },
  { label: "State Bank of India", symbol: "SBIN" },
  { label: "Shree Cement", symbol: "SHREECEM" },
  { label: "Shriram Finance", symbol: "SHRIRAMFIN" },
  { label: "Siemens", symbol: "SIEMENS" },
  { label: "Solar Industries", symbol: "SOLARINDS" },
  { label: "Sona BLW Precision Forgings", symbol: "SONACOMS" },
  { label: "SRF", symbol: "SRF" },
  { label: "Sun Pharmaceutical", symbol: "SUNPHARMA" },
  { label: "Supreme Industries", symbol: "SUPREMEIND" },
  { label: "Suzlon Energy", symbol: "SUZLON" },
  { label: "Swiggy", symbol: "SWIGGY" },
  { label: "Tata Consumer Products", symbol: "TATACONSUM" },
  { label: "Tata Elxsi", symbol: "TATAELXSI" },
  { label: "Tata Power", symbol: "TATAPOWER" },
  { label: "Tata Steel", symbol: "TATASTEEL" },
  { label: "TCS", symbol: "TCS" },
  { label: "Tech Mahindra", symbol: "TECHM" },
  { label: "Tube Investment", symbol: "TIINDIA" },
  { label: "Titan", symbol: "TITAN" },
  { label: "Tata Motors Passenger Vehicles", symbol: "TMPV" },
  { label: "Torrent Pharmaceuticals", symbol: "TORNTPHARM" },
  { label: "Trent", symbol: "TRENT" },
  { label: "TVS Motors", symbol: "TVSMOTOR" },
  { label: "UltraTech Cement", symbol: "ULTRACEMCO" },
  { label: "Union Bank of India", symbol: "UNIONBANK" },
  { label: "United Spirits", symbol: "UNITDSPR" },
  { label: "UNO Minda", symbol: "UNOMINDA" },
  { label: "UPL", symbol: "UPL" },
  { label: "Varun Beverages", symbol: "VBL" },
  { label: "Vedanta", symbol: "VEDL" },
  { label: "Vishal Mega Mart", symbol: "VMM" },
  { label: "Voltas", symbol: "VOLTAS" },
  { label: "Waaree Energies", symbol: "WAAREEENER" },
  { label: "Wipro", symbol: "WIPRO" },
  { label: "Yes Bank", symbol: "YESBANK" },
  { label: "Zydus Life Science", symbol: "ZYDUSLIFE" },

  // ── Large-cap cash equities (Nifty 100 net-new — listed but not yet F&O-tradeable), 3 entries ──
  { label: "Siemens Energy", symbol: "ENRIN" },
  { label: "Tata Capital", symbol: "TATACAP" },
  { label: "Tata Motors", symbol: "TMCV" },

  // ── Midcap cash equities (Nifty Midcap 150 net-new — not in F&O list), 58 entries ──
  { label: "3M India", symbol: "3MINDIA" },
  { label: "Abbott", symbol: "ABBOTINDIA" },
  { label: "ACC", symbol: "ACC" },
  { label: "AIA Engineering", symbol: "AIAENG" },
  { label: "Authum Inv & Infr", symbol: "AIIL" },
  { label: "Ajanta Pharma", symbol: "AJANTPHARM" },
  { label: "Anthem Biosciences", symbol: "ANTHEM" },
  { label: "Apar Industries", symbol: "APARINDS" },
  { label: "Apollo Tyres", symbol: "APOLLOTYRE" },
  { label: "Adani Total Gas", symbol: "ATGL" },
  { label: "AWL Agri Business", symbol: "AWL" },
  { label: "Bajaj Housing Finance", symbol: "BAJAJHFL" },
  { label: "Balkrishna Industries", symbol: "BALKRISIND" },
  { label: "Berger Paints", symbol: "BERGEPAINT" },
  { label: "Bharti Hexacom", symbol: "BHARTIHEXA" },
  { label: "Coromandel International", symbol: "COROMANDEL" },
  { label: "CRISIL", symbol: "CRISIL" },
  { label: "Endurance Technologies", symbol: "ENDURANCE" },
  { label: "Escorts Kubota", symbol: "ESCORTS" },
  { label: "Gujarat Fluorochemicals", symbol: "FLUOROCHEM" },
  { label: "GIC of India", symbol: "GICRE" },
  { label: "GlaxoSmithKline Pharmaceuticals", symbol: "GLAXO" },
  { label: "Godrej Industries", symbol: "GODREJIND" },
  { label: "Groww", symbol: "GROWW" },
  { label: "GE Vernova T&D", symbol: "GVT&D" },
  { label: "HDB Financial Services", symbol: "HDBFS" },
  { label: "Hexaware Technologies", symbol: "HEXT" },
  { label: "Honeywell Automation", symbol: "HONAUT" },
  { label: "HUDCO", symbol: "HUDCO" },
  { label: "ICICI Prudential Asset Management", symbol: "ICICIAMC" },
  { label: "IPCA Laboratories", symbol: "IPCALAB" },
  { label: "IRCTC", symbol: "IRCTC" },
  { label: "ITC Hotels", symbol: "ITCHOTELS" },
  { label: "JK Cement", symbol: "JKCEMENT" },
  { label: "Jindal Stainless", symbol: "JSL" },
  { label: "JSW Infrastructure", symbol: "JSWINFRA" },
  { label: "KPR Mill", symbol: "KPRMILL" },
  { label: "Lenskart Solutions", symbol: "LENSKART" },
  { label: "LG Electronics", symbol: "LGEINDIA" },
  { label: "Linde", symbol: "LINDEINDIA" },
  { label: "Lloyds Metals & Energy", symbol: "LLOYDSME" },
  { label: "L&T Technology Services", symbol: "LTTS" },
  { label: "M&M Financial Services", symbol: "M&MFIN" },
  { label: "Bank of Maharashtra", symbol: "MAHABANK" },
  { label: "Global Health", symbol: "MEDANTA" },
  { label: "MRF", symbol: "MRF" },
  { label: "The New India Assurance Company", symbol: "NIACL" },
  { label: "NLC India", symbol: "NLCINDIA" },
  { label: "NTPC Green Energy", symbol: "NTPCGREEN" },
  { label: "Radico Khaitan", symbol: "RADICO" },
  { label: "Schaeffler India", symbol: "SCHAEFFLER" },
  { label: "SJVN", symbol: "SJVN" },
  { label: "Sundaram Finance", symbol: "SUNDARMFIN" },
  { label: "Tata Communications", symbol: "TATACOMM" },
  { label: "Tata Investment Corporation", symbol: "TATAINVEST" },
  { label: "Thermax", symbol: "THERMAX" },
  { label: "Torrent Power", symbol: "TORNTPOWER" },
  { label: "United Breweries", symbol: "UBL" },

  // ── Smallcap cash equities (Nifty Smallcap 250 net-new — not in F&O list), 230 entries ──
  { label: "Aadhar Housing Finance", symbol: "AADHARHFC" },
  { label: "Aarti Industries", symbol: "AARTIIND" },
  { label: "Aavas Financiers", symbol: "AAVAS" },
  { label: "Allied Blenders & Distillers", symbol: "ABDL" },
  { label: "Aditya Birla Fashion & Retail", symbol: "ABFRL" },
  { label: "Aditya Birla Lifestyle Brands", symbol: "ABLBL" },
  { label: "Aditya Birla Real Estate", symbol: "ABREL" },
  { label: "Aditya Birla Sun Life AMC", symbol: "ABSLAMC" },
  { label: "Action Construction Equipment", symbol: "ACE" },
  { label: "ACME Solar Holdings", symbol: "ACMESOLAR" },
  { label: "Acutaas Chemicals", symbol: "ACUTAAS" },
  { label: "Aegis Logistics", symbol: "AEGISLOG" },
  { label: "Aegis Vopak Terminals", symbol: "AEGISVOPAK" },
  { label: "Afcons Infrastructure", symbol: "AFCONS" },
  { label: "Affle 3i", symbol: "AFFLE" },
  { label: "Anand Rathi Wealth", symbol: "ANANDRATHI" },
  { label: "Anant Raj", symbol: "ANANTRAJ" },
  { label: "Anupam Rasayan", symbol: "ANURAS" },
  { label: "Aptus Value Housing Finance", symbol: "APTUS" },
  { label: "Amara Raja Energy & Mobility", symbol: "ARE&M" },
  { label: "Asahi India Glass", symbol: "ASAHIINDIA" },
  { label: "Aster DM Healthcare", symbol: "ASTERDM" },
  { label: "Ather Energy", symbol: "ATHERENERG" },
  { label: "Atul", symbol: "ATUL" },
  { label: "Balrampur Chini Mills", symbol: "BALRAMCHIN" },
  { label: "Bata", symbol: "BATAINDIA" },
  { label: "Bayer Crop Science", symbol: "BAYERCROP" },
  { label: "Bombay Burmah Trading", symbol: "BBTC" },
  { label: "Belrise Industries", symbol: "BELRISE" },
  { label: "BEML", symbol: "BEML" },
  { label: "Bikaji Foods International", symbol: "BIKAJI" },
  { label: "BLS International Services", symbol: "BLS" },
  { label: "Blue Dart Express", symbol: "BLUEDART" },
  { label: "Blue Jet Healthcare", symbol: "BLUEJET" },
  { label: "Brigade Enterprises", symbol: "BRIGADE" },
  { label: "Birlasoft", symbol: "BSOFT" },
  { label: "Can Fin Homes", symbol: "CANFINHOME" },
  { label: "Canara HSBC Life Insurance Company", symbol: "CANHLIFE" },
  { label: "Caplin Point Laboratories", symbol: "CAPLIPOINT" },
  { label: "Carborundum Universal", symbol: "CARBORUNIV" },
  { label: "CarTrade Tech", symbol: "CARTRADE" },
  { label: "Castrol", symbol: "CASTROLIND" },
  { label: "CCL Products", symbol: "CCL" },
  { label: "CEAT", symbol: "CEATLTD" },
  { label: "Cemindia Projects", symbol: "CEMPRO" },
  { label: "Central Bank of India", symbol: "CENTRALBK" },
  { label: "CESC", symbol: "CESC" },
  { label: "Capri Global Capital", symbol: "CGCL" },
  { label: "Chalet Hotels", symbol: "CHALET" },
  { label: "Chambal Fertilisers & Chemicals", symbol: "CHAMBLFERT" },
  { label: "Chennai Petroleum Corporation", symbol: "CHENNPETRO" },
  { label: "Choice International", symbol: "CHOICEIN" },
  { label: "Cholamandalam Financial Holdings", symbol: "CHOLAHLDNG" },
  { label: "Clean Science & Technology", symbol: "CLEAN" },
  { label: "Cohance Lifesciences", symbol: "COHANCE" },
  { label: "Concord Biotech", symbol: "CONCORDBIO" },
  { label: "Aditya Infotech", symbol: "CPPLUS" },
  { label: "Craftsman Automation", symbol: "CRAFTSMAN" },
  { label: "Credit Access Grameen", symbol: "CREDITACC" },
  { label: "City Union Bank", symbol: "CUB" },
  { label: "Cyient", symbol: "CYIENT" },
  { label: "Data Patterns", symbol: "DATAPATTNS" },
  { label: "DCM Shriram Consolidated", symbol: "DCMSHRIRAM" },
  { label: "Deepak Fertilisers & Petrochemicals", symbol: "DEEPAKFERT" },
  { label: "Deepak Nitrite", symbol: "DEEPAKNTR" },
  { label: "Devyani International", symbol: "DEVYANI" },
  { label: "DOMS Industries", symbol: "DOMS" },
  { label: "eClerx Services", symbol: "ECLERX" },
  { label: "EID Parry", symbol: "EIDPARRY" },
  { label: "EIH Hotels", symbol: "EIHOTEL" },
  { label: "Elecon Engineering Company", symbol: "ELECON" },
  { label: "Elgi Equipments", symbol: "ELGIEQUIP" },
  { label: "Emami", symbol: "EMAMILTD" },
  { label: "Emcure Pharmaceuticals", symbol: "EMCURE" },
  { label: "Emmvee Photovoltaic Power", symbol: "EMMVEE" },
  { label: "Engineers India", symbol: "ENGINERSIN" },
  { label: "Eris Lifesciences", symbol: "ERIS" },
  { label: "Fertilisers & Chemical Travancore", symbol: "FACT" },
  { label: "Finolex Cables", symbol: "FINCABLES" },
  { label: "Firstcry (Brainbees Solutions)", symbol: "FIRSTCRY" },
  { label: "Five Star Business Finance", symbol: "FIVESTAR" },
  { label: "Firstsource Solutions", symbol: "FSL" },
  { label: "Gabriel", symbol: "GABRIEL" },
  { label: "Gallantt Ispat", symbol: "GALLANTT" },
  { label: "Great Eastern Shipping Company", symbol: "GESHIP" },
  { label: "Gillette", symbol: "GILLETTE" },
  { label: "Gland Pharma", symbol: "GLAND" },
  { label: "Gujarat Mineral Development Corporation", symbol: "GMDCLTD" },
  { label: "Go Digit General Insurance", symbol: "GODIGIT" },
  { label: "Godawari Power & Ispat", symbol: "GPIL" },
  { label: "Granules", symbol: "GRANULES" },
  { label: "Graphite", symbol: "GRAPHITE" },
  { label: "Gravita India", symbol: "GRAVITA" },
  { label: "Garden Reach Shipbuilders", symbol: "GRSE" },
  { label: "Gujarat State Petronet", symbol: "GSPL" },
  { label: "HBL Engineering", symbol: "HBLENGINE" },
  { label: "HEG", symbol: "HEG" },
  { label: "HFCL", symbol: "HFCL" },
  { label: "Hindustan Copper", symbol: "HINDCOPPER" },
  { label: "Home First Finance Company", symbol: "HOMEFIRST" },
  { label: "Mamaearth", symbol: "HONASA" },
  { label: "Himadri Speciality Chemical", symbol: "HSCL" },
  { label: "IDBI Bank", symbol: "IDBI" },
  { label: "IFCI", symbol: "IFCI" },
  { label: "International Gemological Institute", symbol: "IGIL" },
  { label: "Indraprastha Gas", symbol: "IGL" },
  { label: "IIFL Finance", symbol: "IIFL" },
  { label: "Inventurus Knowledge Solutions", symbol: "IKS" },
  { label: "Indegene", symbol: "INDGN" },
  { label: "India Cements", symbol: "INDIACEM" },
  { label: "IndiaMART InterMesh", symbol: "INDIAMART" },
  { label: "Intellect Design Arena", symbol: "INTELLECT" },
  { label: "Indian Overseas Bank", symbol: "IOB" },
  { label: "IRB Infrastructure Developers", symbol: "IRB" },
  { label: "Ircon International", symbol: "IRCON" },
  { label: "ITI", symbol: "ITI" },
  { label: "Jammu & Kashmir Bank", symbol: "J&KBANK" },
  { label: "Jain Resource Recycling", symbol: "JAINREC" },
  { label: "J B Chemicals and Pharmaceuticals", symbol: "JBCHEPHARM" },
  { label: "JBM Auto", symbol: "JBMA" },
  { label: "Jindal SAW", symbol: "JINDALSAW" },
  { label: "JK Tyre & Industries", symbol: "JKTYRE" },
  { label: "JM Financial", symbol: "JMFINANCIL" },
  { label: "Jaiprakash Power Ventures", symbol: "JPPOWER" },
  { label: "JSW Cement", symbol: "JSWCEMENT" },
  { label: "JSW Dulux", symbol: "JSWDULUX" },
  { label: "Jubilant Ingrevia", symbol: "JUBLINGREA" },
  { label: "Jubilant Pharmova", symbol: "JUBLPHARMA" },
  { label: "Jupiter Wagons", symbol: "JWL" },
  { label: "Jyoti CNC Automation", symbol: "JYOTICNC" },
  { label: "Kajaria Ceramics", symbol: "KAJARIACER" },
  { label: "Karur Vysya Bank", symbol: "KARURVYSYA" },
  { label: "KEC International", symbol: "KEC" },
  { label: "Krishna Institute of Medical Sciences", symbol: "KIMS" },
  { label: "Kirloskar Oil Engines", symbol: "KIRLOSENG" },
  { label: "Kalpataru Projects International", symbol: "KPIL" },
  { label: "Dr. Lal Path Labs", symbol: "LALPATHLAB" },
  { label: "Latent View Analytics", symbol: "LATENTVIEW" },
  { label: "Lemon Tree Hotels", symbol: "LEMONTREE" },
  { label: "LT Foods", symbol: "LTFOODS" },
  { label: "CE Info Systems", symbol: "MAPMYINDIA" },
  { label: "Meesho", symbol: "MEESHO" },
  { label: "Mahanagar Gas", symbol: "MGL" },
  { label: "Minda Corporation", symbol: "MINDACORP" },
  { label: "MMTC", symbol: "MMTC" },
  { label: "Mangalore Refinery & Petroleum", symbol: "MRPL" },
  { label: "Motherson Sumi Wiring", symbol: "MSUMI" },
  { label: "Natco Pharma", symbol: "NATCOPHARM" },
  { label: "Nava", symbol: "NAVA" },
  { label: "Navin Fluorine International", symbol: "NAVINFLUOR" },
  { label: "NCC", symbol: "NCC" },
  { label: "Netweb Technologies", symbol: "NETWEB" },
  { label: "Neuland Laboratories", symbol: "NEULANDLAB" },
  { label: "Newgen Software Technologies", symbol: "NEWGEN" },
  { label: "Narayana Hrudayalaya", symbol: "NH" },
  { label: "Niva Bupa Health Insurance Company", symbol: "NIVABUPA" },
  { label: "NMDC Steel", symbol: "NSLNISP" },
  { label: "Nuvoco Vistas Corporation", symbol: "NUVOCO" },
  { label: "Ola Electric Mobility", symbol: "OLAELEC" },
  { label: "Olectra Greentech", symbol: "OLECTRA" },
  { label: "Onesource Specialty Pharma", symbol: "ONESOURCE" },
  { label: "Paradeep Phosphates", symbol: "PARADEEP" },
  { label: "PCBL Chemical", symbol: "PCBL" },
  { label: "Pfizer", symbol: "PFIZER" },
  { label: "Pine Labs", symbol: "PINELABS" },
  { label: "Piramal Finance", symbol: "PIRAMALFIN" },
  { label: "Poly Medicure", symbol: "POLYMED" },
  { label: "Poonawalla Fincorp", symbol: "POONAWALLA" },
  { label: "Piramal Pharma", symbol: "PPLPHARMA" },
  { label: "PTC Industries", symbol: "PTCIL" },
  { label: "PVR Inox", symbol: "PVRINOX" },
  { label: "Physicswallah", symbol: "PWL" },
  { label: "Railtel Corporation of India", symbol: "RAILTEL" },
  { label: "Rainbow Childrens Medicare", symbol: "RAINBOW" },
  { label: "Ramco Cements", symbol: "RAMCOCEM" },
  { label: "Redington", symbol: "REDINGTON" },
  { label: "RHI Magnesita", symbol: "RHIM" },
  { label: "RITES", symbol: "RITES" },
  { label: "Ramkrishna Forgings", symbol: "RKFORGE" },
  { label: "Reliance Power", symbol: "RPOWER" },
  { label: "RR Kabel", symbol: "RRKABEL" },
  { label: "Sagility", symbol: "SAGILITY" },
  { label: "Sai Life Sciences", symbol: "SAILIFE" },
  { label: "Sapphire Foods", symbol: "SAPPHIRE" },
  { label: "Sarda Energy & Minerals", symbol: "SARDAEN" },
  { label: "Saregama India", symbol: "SAREGAMA" },
  { label: "SBFC Finance", symbol: "SBFC" },
  { label: "Schneider Electric Infra", symbol: "SCHNEIDER" },
  { label: "Shipping Corporation of India", symbol: "SCI" },
  { label: "Shyam Metalics & Energy", symbol: "SHYAMMETL" },
  { label: "Signatureglobal", symbol: "SIGNATURE" },
  { label: "Sobha", symbol: "SOBHA" },
  { label: "Sonata Software", symbol: "SONATSOFTW" },
  { label: "Supreme Petrochem", symbol: "SPLPETRO" },
  { label: "Star Health Insurance", symbol: "STARHEALTH" },
  { label: "Sumitomo Chemical", symbol: "SUMICHEM" },
  { label: "Sun TV Network", symbol: "SUNTV" },
  { label: "Swan Corp", symbol: "SWANCORP" },
  { label: "Syngene International", symbol: "SYNGENE" },
  { label: "Syrma SGS", symbol: "SYRMA" },
  { label: "Transformers & Rectifiers", symbol: "TARIL" },
  { label: "Tata Chemicals", symbol: "TATACHEM" },
  { label: "Tata Technologies", symbol: "TATATECH" },
  { label: "TBO Tek", symbol: "TBOTEK" },
  { label: "Techno Electric & Engineering", symbol: "TECHNOE" },
  { label: "Tega Industries", symbol: "TEGA" },
  { label: "Tejas Networks", symbol: "TEJASNET" },
  { label: "Tenneco Clean Air", symbol: "TENNIND" },
  { label: "Leela Palaces Hotels & Resorts", symbol: "THELEELA" },
  { label: "Timken", symbol: "TIMKEN" },
  { label: "Titagarh Rail Systems", symbol: "TITAGARH" },
  { label: "Travel Food Services", symbol: "TRAVELFOOD" },
  { label: "Trident", symbol: "TRIDENT" },
  { label: "Triveni Turbines", symbol: "TRITURBINE" },
  { label: "Tata Teleservices Maharashtra", symbol: "TTML" },
  { label: "UCO Bank", symbol: "UCOBANK" },
  { label: "Urban Company", symbol: "URBANCO" },
  { label: "Usha Martin", symbol: "USHAMART" },
  { label: "UTI AMC", symbol: "UTIAMC" },
  { label: "Vijaya Diagnostic Centre", symbol: "VIJAYA" },
  { label: "Vardhman Textiles", symbol: "VTL" },
  { label: "Welspun Corp", symbol: "WELCORP" },
  { label: "Welspun Living", symbol: "WELSPUNLIV" },
  { label: "Whirlpool", symbol: "WHIRLPOOL" },
  { label: "Wockhardt", symbol: "WOCKPHARMA" },
  { label: "Zee Entertainment", symbol: "ZEEL" },
  { label: "Zensar Technologies", symbol: "ZENSARTECH" },
  { label: "Zen Technologies", symbol: "ZENTEC" },
  { label: "ZF Commercial", symbol: "ZFCVINDIA" },
  { label: "Zydus Wellness", symbol: "ZYDUSWELL" },
] as const;

/** Adapter for ``components/ui/autocomplete`` which expects ``value``
 *  (not ``symbol``) as the canonical-id field. KNOWN_SYMBOLS keeps the
 *  ``symbol`` name for backwards compat with its existing public
 *  shape; this private constant transforms it once at module load. */
const AUTOCOMPLETE_ITEMS: ReadonlyArray<{ label: string; value: string }> =
  KNOWN_SYMBOLS.map((s) => ({ label: s.label, value: s.symbol }));

const TIMEFRAMES: readonly CandleTimeframe[] = ["1m", "5m", "15m", "1h", "1d"] as const;

/** Build a sensible default Dhan request — last 90 days at 5m. */
export function defaultCandlesRequest(): CandlesRequestPayload {
  const now = new Date();
  const ninetyDaysAgo = new Date(now);
  ninetyDaysAgo.setDate(ninetyDaysAgo.getDate() - 89);
  return {
    symbol: "NIFTY",
    timeframe: "5m",
    from_date: ninetyDaysAgo.toISOString(),
    to_date: now.toISOString(),
  };
}

/** Default value for first render. ``defaultSource`` lets each
 * builder pre-select Synthetic (intermediate) or Real Dhan (expert). */
export function makeDefaultPickerValue(
  defaultSource: CandleSource = "synthetic",
): CandleSourcePickerValue {
  return {
    source: defaultSource,
    candles_request:
      defaultSource === "dhan_historical" ? defaultCandlesRequest() : null,
    validation_error: "",
  };
}

export function CandleSourcePicker({
  value,
  onChange,
  forceDhan = false,
  compactHint = false,
}: Props) {
  const headingId = useId();
  // Stable fallback for the render-path ``value.candles_request ??``
  // guard below. Calling ``defaultCandlesRequest()`` inline every
  // render produces a fresh ``new Date()`` and breaks downstream
  // ``React.memo`` short-circuiting on ``<DhanForm>``. Memoising once
  // per component instance pins the fallback to "now at first mount".
  const fallbackRequest = useMemo(() => defaultCandlesRequest(), []);

  const handleSourceChange = (next: CandleSource) => {
    if (next === "dhan_historical") {
      onChange({
        source: "dhan_historical",
        candles_request: value.candles_request ?? defaultCandlesRequest(),
        validation_error: "",
      });
    } else {
      onChange({ source: "synthetic", candles_request: null, validation_error: "" });
    }
  };

  const handleRequestChange = (
    next: Partial<CandlesRequestPayload>,
  ) => {
    const merged: CandlesRequestPayload = {
      ...(value.candles_request ?? fallbackRequest),
      ...next,
    };
    onChange({
      source: "dhan_historical",
      candles_request: merged,
      validation_error: validateRequest(merged),
    });
  };

  const showDhanForm =
    forceDhan || value.source === "dhan_historical";

  return (
    <GlassmorphismCard hover={false} className="space-y-3">
      <div className="flex items-center gap-2">
        <CandlestickChart className="h-4 w-4 text-accent-blue" aria-hidden />
        <h3 id={headingId} className="text-sm font-semibold">
          Candle source
        </h3>
        {forceDhan ? null : (
          <Badge className="ml-auto text-[10px] bg-white/[0.06] border-white/[0.1]">
            backtest data
          </Badge>
        )}
      </div>

      {forceDhan ? null : (
        <SourceToggle source={value.source} onChange={handleSourceChange} />
      )}

      {showDhanForm ? (
        <DhanForm
          request={value.candles_request ?? fallbackRequest}
          onChange={handleRequestChange}
          validationError={value.validation_error}
          compactHint={compactHint}
        />
      ) : (
        <SyntheticHint />
      )}
    </GlassmorphismCard>
  );
}

// ─── Source toggle ─────────────────────────────────────────────────────

function SourceToggle({
  source,
  onChange,
}: {
  source: CandleSource;
  onChange: (next: CandleSource) => void;
}) {
  return (
    <div role="tablist" aria-label="Candle source" className="grid grid-cols-2 gap-2">
      <ToggleButton
        active={source === "synthetic"}
        onClick={() => onChange("synthetic")}
        icon={Sparkles}
        label="Synthetic"
        sub="Quick test (120 bars)"
      />
      <ToggleButton
        active={source === "dhan_historical"}
        onClick={() => onChange("dhan_historical")}
        icon={Database}
        label="Real Dhan data"
        sub="Pull from your subscription"
      />
    </div>
  );
}

function ToggleButton({
  active,
  onClick,
  icon: Icon,
  label,
  sub,
}: {
  active: boolean;
  onClick: () => void;
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  sub: string;
}) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      onClick={onClick}
      className={cn(
        "flex items-start gap-2 rounded-md border p-2.5 text-left transition-colors",
        active
          ? "border-accent-blue/40 bg-accent-blue/[0.08]"
          : "border-white/[0.08] bg-white/[0.02] hover:bg-white/[0.04]",
      )}
    >
      <Icon
        className={cn(
          "h-4 w-4 shrink-0 mt-0.5",
          active ? "text-accent-blue" : "text-muted-foreground",
        )}
      />
      <div className="space-y-0.5">
        <div
          className={cn("text-xs font-medium", active ? "text-accent-blue" : "")}
        >
          {label}
        </div>
        <div className="text-[10px] text-muted-foreground">{sub}</div>
      </div>
    </button>
  );
}

// ─── Synthetic hint ────────────────────────────────────────────────────

function SyntheticHint() {
  return (
    <p className="text-[12px] text-muted-foreground leading-snug">
      120-bar deterministic series. Fast and reproducible — best for
      sanity-checking strategy logic before pulling real data.
    </p>
  );
}

// ─── Dhan form ─────────────────────────────────────────────────────────

function DhanForm({
  request,
  onChange,
  validationError,
  compactHint,
}: {
  request: CandlesRequestPayload;
  onChange: (next: Partial<CandlesRequestPayload>) => void;
  validationError: string;
  compactHint: boolean;
}) {
  const fromInputId = useId();
  const toInputId = useId();
  const symbolInputId = useId();
  const timeframeInputId = useId();

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        <FormField label="Symbol" htmlFor={symbolInputId}>
          {/* Base UI Autocomplete (Step 3) — replaces the native
              ``<datalist>`` which became qualitatively broken on
              mobile at this scale (216 entries). Free-text fallback
              is preserved: ``onValueChange`` fires on every keystroke,
              including non-matching values, and the backend's
              normalise_symbol resolves them via canonical + alias map.
              The ``.toUpperCase()`` mirrors the original input's
              keystroke handler — backend-side resolution is case-
              insensitive, but uppercased values match the canonical
              KNOWN_SYMBOLS keys directly without going through the
              alias path. */}
          <Autocomplete
            id={symbolInputId}
            value={request.symbol}
            onValueChange={(value) =>
              onChange({ symbol: value.toUpperCase() })
            }
            items={AUTOCOMPLETE_ITEMS}
            placeholder="Type to search F&O + equity symbols…"
          />
        </FormField>

        <FormField label="Timeframe" htmlFor={timeframeInputId}>
          <select
            id={timeframeInputId}
            value={request.timeframe}
            onChange={(e) =>
              onChange({ timeframe: e.target.value as CandleTimeframe })
            }
            className="w-full rounded-md bg-white/[0.04] border border-white/[0.08] px-2 py-1.5 text-xs"
          >
            {TIMEFRAMES.map((tf) => (
              <option key={tf} value={tf}>
                {tf}
              </option>
            ))}
          </select>
        </FormField>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        <FormField label="From (UTC)" htmlFor={fromInputId}>
          <input
            id={fromInputId}
            type="datetime-local"
            value={toLocalInput(request.from_date)}
            onChange={(e) => onChange({ from_date: fromLocalInput(e.target.value) })}
            className="w-full rounded-md bg-white/[0.04] border border-white/[0.08] px-2 py-1.5 text-xs"
          />
        </FormField>
        <FormField label="To (UTC)" htmlFor={toInputId}>
          <input
            id={toInputId}
            type="datetime-local"
            value={toLocalInput(request.to_date)}
            onChange={(e) => onChange({ to_date: fromLocalInput(e.target.value) })}
            className="w-full rounded-md bg-white/[0.04] border border-white/[0.08] px-2 py-1.5 text-xs"
          />
        </FormField>
      </div>

      {validationError ? (
        <p className="text-[11px] text-loss leading-snug">{validationError}</p>
      ) : null}

      <p className="text-[11px] text-muted-foreground leading-snug">
        {compactHint
          ? "Server-side symbol resolution — pick from the autocomplete or type freely."
          : "Autocomplete covers F&O indices, F&O stocks, and Nifty 500 cash equities " +
            "(e.g., NIFTY, BANKNIFTY, RELIANCE, ENRIN, AARTIIND). " +
            "Free-text input is allowed — the server resolves via canonical / alias map. " +
            "Real-data fetches require ``DHAN_ACCESS_TOKEN`` configured server-side."}
      </p>
    </div>
  );
}

function FormField({
  label,
  htmlFor,
  children,
}: {
  label: string;
  htmlFor: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1">
      <label
        htmlFor={htmlFor}
        className="text-[10px] uppercase tracking-wide text-muted-foreground font-medium"
      >
        {label}
      </label>
      {children}
    </div>
  );
}

// ─── Beginner-mode hint card ──────────────────────────────────────────

export function BeginnerSyntheticHint() {
  return (
    <div className="rounded-md border border-white/[0.08] bg-white/[0.02] p-3 flex items-start gap-2">
      <Sparkles className="h-4 w-4 text-accent-blue mt-0.5 shrink-0" />
      <div className="space-y-0.5">
        <p className="text-xs font-medium">Synthetic data</p>
        <p className="text-[11px] text-muted-foreground leading-snug">
          Backtest synthetic 120-bar series par chalega — beginner mode mein
          yeh default hai. Real market data se backtest karne ke liye
          Intermediate ya Expert mode use karo.
        </p>
      </div>
    </div>
  );
}

// ─── Validation + storage helpers (exported for builders) ─────────────

/** Returns a Hinglish error string, or empty string if valid. */
export function validateRequest(req: CandlesRequestPayload): string {
  if (!req.symbol.trim()) return "Symbol khaali nahi ho sakta.";
  const from = new Date(req.from_date);
  const to = new Date(req.to_date);
  if (Number.isNaN(from.getTime()) || Number.isNaN(to.getTime())) {
    return "Date format galat hai.";
  }
  if (from >= to) return "From date To date se chhoti honi chahiye.";
  if (req.timeframe !== "1d") {
    const days = (to.getTime() - from.getTime()) / 86_400_000;
    if (days > 90) return "Intraday window 90 din se zyada nahi ho sakti.";
  }
  return "";
}

const STORAGE_KEY = "tradetri:next_candles_request";

/** Stash a request for the next backtest page mount to consume. */
export function stashCandlesRequest(value: CandleSourcePickerValue): void {
  if (typeof window === "undefined") return;
  if (
    value.source !== "dhan_historical"
    || value.candles_request === null
    || value.validation_error !== ""
  ) {
    window.localStorage.removeItem(STORAGE_KEY);
    return;
  }
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(value.candles_request));
}

/** Read and clear the stashed request — one-shot consume. */
export function consumeStashedCandlesRequest(): CandlesRequestPayload | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(STORAGE_KEY);
  if (!raw) return null;
  window.localStorage.removeItem(STORAGE_KEY);
  try {
    const parsed = JSON.parse(raw) as CandlesRequestPayload;
    if (
      typeof parsed.symbol !== "string"
      || typeof parsed.timeframe !== "string"
      || typeof parsed.from_date !== "string"
      || typeof parsed.to_date !== "string"
    ) {
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

// ─── Local-input ↔ ISO conversion ─────────────────────────────────────

/** ``2026-04-07T15:30:00Z`` → ``2026-04-07T15:30`` (HTML datetime-local). */
function toLocalInput(iso: string): string {
  try {
    return iso.slice(0, 16);
  } catch {
    return "";
  }
}

/** ``2026-04-07T15:30`` (datetime-local) → ``2026-04-07T15:30:00Z``. */
function fromLocalInput(local: string): string {
  if (!local) return new Date().toISOString();
  return new Date(local + ":00Z").toISOString();
}

