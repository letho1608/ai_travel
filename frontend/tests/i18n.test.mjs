import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import ts from "typescript";

const source=readFileSync(new URL("../components/LocaleProvider.tsx",import.meta.url),"utf8");
const coreSource=readFileSync(new URL("../lib/i18n-core.ts",import.meta.url),"utf8");
const plannerSource=readFileSync(new URL("../components/Planner.tsx",import.meta.url),"utf8");
const workspaceSource=readFileSync(new URL("../lib/workspace-translations.ts",import.meta.url),"utf8");
const inventorySource=readFileSync(new URL("../lib/inventory-translations.ts",import.meta.url),"utf8");
const exploreSource=readFileSync(new URL("../app/explore/page.tsx",import.meta.url),"utf8");
const roadtripSource=readFileSync(new URL("../lib/roadtrip-translations.ts",import.meta.url),"utf8");
const roadtripPageSource=readFileSync(new URL("../app/roadtrip/page.tsx",import.meta.url),"utf8");
const planViewSource=readFileSync(new URL("../components/PlanView.tsx",import.meta.url),"utf8");
const layoutSource=readFileSync(new URL("../app/layout.tsx",import.meta.url),"utf8");
const navigationSource=readFileSync(new URL("../components/Navigation.tsx",import.meta.url),"utf8");
const footerSource=readFileSync(new URL("../components/Footer.tsx",import.meta.url),"utf8");
const mapViewSource=readFileSync(new URL("../components/MapView.tsx",import.meta.url),"utf8");
const roadTripMapSource=readFileSync(new URL("../components/RoadTripMap.tsx",import.meta.url),"utf8");
const globalsSource=readFileSync(new URL("../app/globals.css",import.meta.url),"utf8");
const adminPageSource=readFileSync(new URL("../app/admin/page.tsx",import.meta.url),"utf8");
const historyPageSource=readFileSync(new URL("../app/history/page.tsx",import.meta.url),"utf8");
const supportPageSource=readFileSync(new URL("../app/support/page.tsx",import.meta.url),"utf8");
const apiSource=readFileSync(new URL("../lib/api.ts",import.meta.url),"utf8");
const nextConfigSource=readFileSync(new URL("../next.config.mjs",import.meta.url),"utf8");
const backendPlanSource=readFileSync(new URL("../../backend/app/routers/plans.py",import.meta.url),"utf8");
const backendConfigSource=readFileSync(new URL("../../backend/app/config.py",import.meta.url),"utf8");
const backendDataSource=readFileSync(new URL("../../backend/app/data.py",import.meta.url),"utf8");
const backendMainSource=readFileSync(new URL("../../backend/app/main.py",import.meta.url),"utf8");
const googlePlacesSource=readFileSync(new URL("../../backend/app/services/google_places.py",import.meta.url),"utf8");
const runBatSource=readFileSync(new URL("../../run.bat",import.meta.url),"utf8");
const compiled=ts.transpileModule(coreSource,{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText;
const core=await import(`data:text/javascript;base64,${Buffer.from(compiled).toString("base64")}`);
const compiledApi=ts.transpileModule(apiSource,{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText;
const api=await import(`data:text/javascript;base64,${Buffer.from(compiledApi).toString("base64")}`);

test("rendered brand palette uses Hanoi green without legacy purple",()=>{
  const controlled=[globalsSource,mapViewSource,roadTripMapSource].join("\n").toLowerCase();
  for(const green of ["#086b27","#075a22","#5fa858","#e3efe0","#f3faf1"])assert.match(controlled,new RegExp(green),`missing green ${green}`);
  for(const purple of ["#7d4fb8","#ae86f7","#cdb3ff","#efe7fd","#f7f3fe","#4b2c82","#926cd6"])assert.doesNotMatch(controlled,new RegExp(purple),`legacy purple ${purple}`);
  assert.match(mapViewSource,/#bb4d45/);
  assert.match(roadTripMapSource,/#bb4d45/);
  assert.match(globalsSource,/:root\{--ink:#0f172a;/);
  assert.match(globalsSource,/@media\(prefers-color-scheme:dark\)\{[\s\S]*--paper:#0d1710;[\s\S]*--surface:#132419;[\s\S]*--green-soft:#173528/);
  assert.match(globalsSource,/--danger:#bb4d45;--danger-soft:#f0dad7;--info:#536fac;--info-soft:#dde3ee/);
  assert.match(globalsSource,/--container:none/);
  assert.match(globalsSource,/\.workspace-page\{max-width:none;margin:0;padding:0 20px\}/);
  assert.match(globalsSource,/\.history-page\{max-width:none;margin:0;padding:0 24px 48px\}/);
});
test("site logo uses the provided travel assistant image",()=>{
  const mark=readFileSync(new URL("../public/brand/logo-mark.png",import.meta.url));
  const favicon=readFileSync(new URL("../public/brand/favicon.png",import.meta.url));
  assert.equal(mark.readUInt32BE(16),256);
  assert.equal(mark.readUInt32BE(20),256);
  assert.ok(mark.length<220_000);
  assert.equal(favicon.readUInt32BE(16),180);
  assert.equal(favicon.readUInt32BE(20),180);
  assert.ok(favicon.length<120_000);
  assert.match(navigationSource,/className="brand"[\s\S]*src="\/brand\/logo-mark\.png"/);
  assert.match(footerSource,/className="footer-brand"[\s\S]*src="\/brand\/logo-mark\.png"/);
  assert.match(layoutSource,/icons:\s*\{\s*icon:\s*"\/brand\/favicon\.png",\s*apple:\s*"\/brand\/favicon\.png"\s*\}/);
  assert.match(globalsSource,/\.brand img\{width:\d+px;height:\d+px;border-radius:50%;object-fit:cover/);
  assert.match(globalsSource,/\.footer-brand img\{width:32px;height:32px;border-radius:50%;object-fit:cover/);
  assert.doesNotMatch(globalsSource,/\.brand::before/);
  assert.doesNotMatch(globalsSource,/\.footer-brand::before/);
});

test("login navigation action matches the account pill treatment",()=>{
  assert.match(navigationSource,/className="nav-cta"[\s\S]*className="nav-account-icon"[\s\S]*t\("login"\)/);
  assert.match(globalsSource,/\.nav\{[^}]*z-index:900/);
  assert.match(globalsSource,/\.nav\{[^}]*background:var\(--paper\);[^}]*border-bottom:1px solid var\(--line\)/);
  assert.match(globalsSource,/\.nav\{[^}]*justify-content:space-between;[^}]*width:100%/);
  assert.match(globalsSource,/\.nav-links\{[^}]*margin-left:auto/);
  assert.match(globalsSource,/\.nav-links a\.nav-cta\{display:inline-flex;align-items:center;justify-content:center;gap:7px;min-height:38px;[\s\S]*background:#086b27;[\s\S]*border-radius:var\(--radius-full\)/);
  assert.match(globalsSource,/\.nav-account-icon\{width:17px;height:17px;[\s\S]*stroke:currentColor/);
  assert.match(globalsSource,/@media\(prefers-color-scheme:dark\)\{\.nav-links a\.nav-cta\{border-color:var\(--brand\)\}\.nav-links a\.nav-cta:hover\{border-color:var\(--brand-hover\)\}\}/);
});
const compiledWorkspace=ts.transpileModule(workspaceSource,{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText;
const workspace=await import(`data:text/javascript;base64,${Buffer.from(compiledWorkspace).toString("base64")}`);
const compiledInventory=ts.transpileModule(inventorySource,{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText;
const inventory=await import(`data:text/javascript;base64,${Buffer.from(compiledInventory).toString("base64")}`);
const compiledRoadtrip=ts.transpileModule(roadtripSource,{compilerOptions:{module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2022}}).outputText;
const roadtrip=await import(`data:text/javascript;base64,${Buffer.from(compiledRoadtrip).toString("base64")}`);
const locales=core.supportedLocales;
const keys=core.baseTranslationKeys;
const loginKeys=core.loginTranslationKeys;
const settingsKeys=core.settingsTranslationKeys;
const plannerKeys=core.plannerTranslationKeys;
const workspaceKeys=[...core.workspaceTranslationKeys,...core.resultTranslationKeys];
const inventoryKeys=core.inventoryTranslationKeys;
const roadtripKeys=core.roadtripTranslationKeys;
const assertKey=(line,key,locale)=>{const pattern=new RegExp(`(?:^|[, {])"?${key}"?:"[^"\\s][^"]*"`,"g");const matches=line.match(pattern)||[];assert.equal(matches.length,1,`${locale} must contain exactly one non-blank ${key}`)};

test("all supported locales contain the complete UI contract",()=>{
  for(const locale of locales){
    const line=source.split("\n").find(value=>value.trimStart().startsWith(`${locale}:{`));
    assert.ok(line,`missing locale ${locale}`);
    for(const key of keys)assertKey(line,key,locale);
  }
});

test("all supported locales contain the complete settings contract",()=>{
  for(const locale of locales){
    const line=source.split("\n").find(value=>value.trimStart().startsWith(`${locale}:{`)&&value.includes("personalOptions"));
    assert.ok(line,`missing settings locale ${locale}`);
    for(const key of settingsKeys)assertKey(line,key,locale);
  }
});

test("all supported locales contain the complete login contract",()=>{
  for(const locale of locales){
    const line=source.split("\n").find(value=>value.trimStart().startsWith(`${locale}:{`)&&value.includes("accountEyebrow"));
    assert.ok(line,`missing login locale ${locale}`);
    for(const key of loginKeys)assertKey(line,key,locale);
  }
});

test("all supported locales contain the complete planner contract",()=>{
  for(const locale of locales){
    const line=source.split("\n").find(value=>value.trimStart().startsWith(`${locale}:{`)&&value.includes("heroEyebrow"));
    assert.ok(line,`missing planner locale ${locale}`);
    for(const key of plannerKeys)assertKey(line,key,locale);
  }
  const viLine=source.split("\n").find(value=>value.trimStart().startsWith("vi:{")&&value.includes("heroEyebrow"));
  assert.match(viLine,/destinationPrompt:"Bạn muốn đi ở đâu\?"/);
});

test("workspace catalog covers its typed contract and all locales",()=>{
  for(const locale of locales){
    assert.ok(workspace.workspaceTranslations[locale],`missing workspace locale ${locale}`);
    for(const key of workspaceKeys)assert.equal(typeof workspace.workspaceTranslations[locale][key],"string",`missing ${locale} workspace.${key}`);
  }
  assert.match(source,/workspaceTranslations\[locale\]/);
  const tokens=value=>[...value.matchAll(/\{([^}]+)\}/g)].map(match=>match[1]).sort();
  for(const locale of locales)for(const key of workspaceKeys)assert.deepEqual(tokens(workspace.workspaceTranslations[locale][key]),tokens(workspace.workspaceTranslations.en[key]),`${locale}.${key} must preserve placeholders`);
  assert.equal(workspace.workspaceTranslations.vi.share,"Chia sẻ");
  assert.equal(workspace.workspaceTranslations.vi.downloadPdf,"Tải PDF");
  assert.equal(workspace.workspaceTranslations.vi.itinerary,"Lịch trình");
  assert.equal(workspace.workspaceTranslations.vi.tripSummary,"Tóm tắt chuyến đi");
  assert.equal(workspace.workspaceTranslations.vi.savePlan,"Lưu kế hoạch");
  assert.equal(workspace.workspaceTranslations.vi.regenerate,"Yêu cầu AI tạo lại lịch trình khác");
  assert.equal(workspace.workspaceTranslations.vi.planSaved,"Đã lưu kế hoạch");
});

test("inventory catalog covers its typed contract and all locales",()=>{
  const tokens=value=>[...value.matchAll(/\{([^}]+)\}/g)].map(match=>match[1]).sort();
  for(const locale of locales){
    const line=inventorySource.split("\n").find(value=>value.trimStart().startsWith(`${locale}:{`));
    assert.ok(line,`missing inventory locale ${locale}`);
    for(const key of inventoryKeys){assertKey(line,key,`${locale} inventory`);assert.deepEqual(tokens(inventory.inventoryTranslations[locale][key]),tokens(inventory.inventoryTranslations.en[key]),`${locale}.${key} must preserve placeholders`)}
  }
  assert.doesNotMatch(inventorySource,/\.\.\.en|:\s*en[,}]/);
  assert.match(source,/inventoryTranslations\[locale\]/);
});

test("inventory requests and provider data fail safely",()=>{
  assert.match(exploreSource,/setTimeout\(\(\)=>controller\.abort\(\),30000\)/);
  assert.match(exploreSource,/busyRef\.current/);assert.match(exploreSource,/pendingOffer/);
  assert.match(exploreSource,/getSession\(\)/);assert.match(exploreSource,/isSearchResult/);
  assert.match(exploreSource,/response\.status===401/);assert.match(exploreSource,/removeItem\("auth_token"\)/);
  assert.match(exploreSource,/new URL\(value\)\.protocol==="https:"/);
  assert.doesNotMatch(exploreSource,/data\.detail|error\.message|reason\.message/);
  assert.match(exploreSource,/new Intl\.NumberFormat\(locale,/);assert.match(exploreSource,/aria-selected=/);
});

test("roadtrip catalog covers its typed contract and all locales",()=>{
  const tokens=value=>[...value.matchAll(/\{([^}]+)\}/g)].map(match=>match[1]).sort();
  for(const locale of locales){
    const catalog=roadtrip.roadtripTranslations[locale];
    assert.ok(catalog,`missing roadtrip locale ${locale}`);
    assert.deepEqual(Object.keys(catalog).sort(),[...roadtripKeys].sort(),`${locale} roadtrip must match typed keys exactly`);
    for(const key of roadtripKeys){assert.ok(catalog[key].trim(),`${locale}.${key} must be non-blank`);assert.deepEqual(tokens(catalog[key]),tokens(roadtrip.roadtripTranslations.en[key]),`${locale}.${key} must preserve placeholders`)}
  }
  assert.doesNotMatch(roadtripSource,/\.\.\.en|:\s*en[,}]/);
  assert.match(source,/roadtripTranslations\[locale\]/);
});

test("roadtrip requests and route data fail safely",()=>{
  assert.match(roadtripPageSource,/function inventoryDates\(index:number\)/);
  assert.match(roadtripPageSource,/function nextStop\(items:Stop\[\],withInventory:boolean,label:string\):Stop/);
  assert.match(roadtripPageSource,/Number\(\(\(previous\?\.location\.lat\?\?21\)\+0\.08\)\.toFixed\(4\)\)/);
  assert.match(roadtripPageSource,/function hasDuplicateCoordinates\(items:Stop\[\]\):boolean/);
  assert.match(roadtripPageSource,/new Set\(keys\)\.size!==keys\.length/);
  assert.match(roadtripPageSource,/hasDuplicateCoordinates\(stops\)\)return t\("invalidCoordinates"\)/);
  assert.match(roadtripPageSource,/if\(checked\)setStops\(items=>items\.map\(withInventoryDefaults\)\)/);
  assert.match(roadtripPageSource,/onClick=\{addStop\}/);
  assert.match(roadtripPageSource,/setTimeout\(\(\)=>controller\.abort\(\),30000\)/);
  assert.match(roadtripPageSource,/MAX_RESPONSE_BYTES=4_194_304/);
  assert.match(roadtripPageSource,/busyRef\.current/);
  assert.match(roadtripPageSource,/generation\.current===token/);
  assert.match(roadtripPageSource,/getSession\(\)/);
  assert.match(roadtripPageSource,/function parseRoute/);
  assert.match(roadtripPageSource,/function parsePlan/);
  assert.match(roadtripPageSource,/expires<=now/);
  assert.doesNotMatch(roadtripPageSource,/data\.detail|error\.message|cause\.message===data/);
  assert.match(roadtripPageSource,/new Intl\.NumberFormat\(locale,/);
  assert.match(roadtripPageSource,/label=\{t\("mapLabel"\)\}/);
});

test("workspace mutations fail safely and guard duplicate actions",()=>{
  assert.match(planViewSource,/if\(busyRef\.current\)return false/);
  assert.match(planViewSource,/async function copyShareLink/);
  assert.match(planViewSource,/navigator\.clipboard&&window\.isSecureContext/);
  assert.match(planViewSource,/navigator\.clipboard\.writeText\(value\)/);
  assert.match(planViewSource,/document\.execCommand\("copy"\)/);
  assert.match(planViewSource,/type BusyAction="save"\|"copy"\|"download"/);
  assert.match(planViewSource,/function downloadJson\(\)\{if\(!start\("download"\)\)return/);
  assert.match(planViewSource,/document\.body\.appendChild\(anchor\)/);
  assert.match(planViewSource,/anchor\?\.remove\(\);if\(url\)URL\.revokeObjectURL\(url\);finish\(\)/);
  assert.match(planViewSource,/async function safeJson/);
  assert.match(planViewSource,/catch\{fail\("actionFailed"\)/);
  assert.match(planViewSource,/localStorage\.setItem\(`offline-plan:/);
  assert.match(planViewSource,/function saveOffline\(\)\{if\(!start\("save"\)\)return/);
  assert.match(planViewSource,/setMessage\(\{key:"planSaved"\}\)/);
  assert.match(planViewSource,/className=\{`action-toast \$\{errorMessageKeys\.has\(message\.key\)\s*\?\s*"error"\s*:\s*"success"\}`\}[^>]*role="status"[^>]*aria-live="polite"[^>]*aria-atomic="true"/);
  assert.match(planViewSource,/setMessage\(\(?current\)?\s*=>\s*current\?\?\{key:"commentsFailed"\}\)/);
  assert.match(planViewSource,/body:JSON\.stringify\(\{ma_phien:session,nonce\}\),?\},90000,?/);
  assert.match(planViewSource,/setMessage\(\{key:"regenerateSuccess"\}\)/);
  assert.match(globalsSource,/\.action-toast\{position:fixed/);
  assert.match(globalsSource,/\.action-toast\.error\{[^}]*background:#9f2f20/);
  assert.match(globalsSource,/\.itinerary-summary-actions \.primary\{[^}]*background:#086b27/);
  assert.match(globalsSource,/\.itinerary-summary-actions \.secondary\{[^}]*background:#f3f2ee/);
  assert.match(globalsSource,/\.itinerary-summary-actions \.primary>span\{background-image:url\("data:image\/svg\+xml[^}]*M6\.75/);
  assert.match(globalsSource,/\.itinerary-summary-actions \.secondary>span\{background-image:url\("data:image\/svg\+xml[^}]*circle/);
  assert.match(planViewSource,/className="itinerary-export-actions"[\s\S]*itinerary\.pdf[\s\S]*t\("downloadPdf"\)[\s\S]*calendar\.ics[\s\S]*t\("addCalendar"\)[\s\S]*className="itinerary-summary-actions"/);
  assert.doesNotMatch(planViewSource,/className="trip-actions export-actions"/);
  assert.match(globalsSource,/\.itinerary-export-actions,\.itinerary-summary-actions\{display:grid;grid-template-columns:1fr 1fr;gap:10px\}/);
  assert.match(globalsSource,/\.itinerary-export-actions \.button-link\{[^}]*min-height:44px;[^}]*border:1px solid var\(--line-2\);[^}]*background:var\(--surface\);[^}]*color:var\(--ink\)/);
  assert.match(globalsSource,/\.itinerary-export-actions \.button-link:hover\{border-color:var\(--brand\);background:var\(--green-soft\);color:var\(--brand\);transform:none\}/);
  assert.match(globalsSource,/\.itinerary-export-actions svg\{[^}]*stroke:currentColor/);
  assert.match(planViewSource,/viewBox="0 0 24 24"[\s\S]*M6 3h9l3 3v15H6z[\s\S]*viewBox="0 0 24 24"[\s\S]*M8 2v4M16 2v4M3 9h18/);
  assert.doesNotMatch(planViewSource,/className="itinerary-summary"/);
  assert.equal((planViewSource.match(/className="itinerary-panel card"/g)||[]).length,1);
  assert.match(planViewSource,/className="itinerary-card-hero"/);
  assert.doesNotMatch(planViewSource,/itinerary-summary-badge/);
  assert.match(planViewSource,/slot\.bat_dau/);
  assert.match(planViewSource,/slot\.ket_thuc/);
  assert.match(planViewSource,/slot\.mo_ta/);
  assert.match(planViewSource,/slot\.chi_phi/);
  assert.match(planViewSource,/slot\.ghi_chu/);
  assert.match(planViewSource,/slot\.nguon_url/);
  assert.match(planViewSource,/onClick=\{regenerate\} disabled=\{disabled\}/);
  assert.doesNotMatch(planViewSource,/data\.detail|error\.message/);
  assert.match(planViewSource,/className="slot-select"/);
  assert.match(mapViewSource,/function placeReviewLinks\(slot: Slot\)/);
  assert.match(mapViewSource,/google\.com\/search\?q=\$\{query\}/);
  assert.match(mapViewSource,/tiktok\.com\/search\?q=\$\{query\}/);
  assert.match(mapViewSource,/slot\.google_maps_url \|\|/);
  assert.match(mapViewSource,/query_place_id=\$\{encodeURIComponent\(placeId\)\}/);
  assert.match(mapViewSource,/google\.com\/maps\/search\/\?api=1&query=\$\{mapQuery\}/);
  assert.match(googlePlacesSource,/GOOGLE_TEXT_SEARCH_URL/);
  assert.match(googlePlacesSource,/query_text = f"\{name\} Việt Nam"/);
  assert.doesNotMatch(googlePlacesSource,/query_text = f"\{name\} \{area_hint\} Hà Nội"/);
  assert.match(googlePlacesSource,/include_hours: bool = False/);
  assert.match(googlePlacesSource,/if include_photos:\s*field_mask \+= ",places\.photos"/);
  assert.match(googlePlacesSource,/if settings\.google_places_runtime_photos and photo_name:\s*slot\["anh"\] = _photo_url/);
  assert.match(googlePlacesSource,/places\.currentOpeningHours,places\.regularOpeningHours,places\.businessStatus/);
  assert.match(googlePlacesSource,/google_regular_opening_hours/);
  assert.match(googlePlacesSource,/google_current_opening_hours/);
  assert.match(googlePlacesSource,/_quota_available\(\s*cache,\s*"hours"/);
  assert.match(backendConfigSource,/google_places_runtime_hours: bool = False/);
  assert.match(backendConfigSource,/GOOGLE_PLACES_RUNTIME_HOURS/);
  assert.match(backendDataSource,/PLACES_DATA_FILE/);
  assert.match(backendDataSource,/Path\(configured_path\)/);
  assert.match(backendDataSource,/"configured_path": configured_path/);
  assert.match(backendMainSource,/places_data_file/);
  assert.match(backendMainSource,/places_count/);
  assert.match(runBatSource,/if "%PLACES_DATA_FILE%"=="" set "PLACES_DATA_FILE=vietnam_places\.json"/);
  assert.match(runBatSource,/findstr \/C:"%PLACES_DATA_FILE%"/);
  assert.match(runBatSource,/set "PLACES_DATA_FILE=%PLACES_DATA_FILE%"/);
  assert.match(mapViewSource,/rel="noopener noreferrer"/);
  assert.match(mapViewSource,/Xem thêm thông tin về địa điểm này trên:/);
  assert.match(globalsSource,/\.map-popup p\{[^}]*font-size:12px/);
  assert.match(globalsSource,/\.map-popup-actions\{display:grid;grid-template-columns:repeat\(3,1fr\);gap:6px\}/);
  assert.match(globalsSource,/\.map-panel\{[^}]*min-width:0;position:relative;z-index:0\}\.map-panel \.map\{[^}]*position:relative;z-index:0;isolation:isolate/);
  assert.match(planViewSource,/ten_dia_diem_thay_the:replacementText\?\.trim\(\)\|\|undefined/);
  assert.match(planViewSource,/role="combobox" aria-autocomplete="list"/);
  assert.match(planViewSource,/void swipe\(slot\.dia_diem_id,undefined,searchText\)/);
  assert.match(globalsSource,/\.slot-actions\{grid-column:1\/-1;[^}]*justify-self:end/);
  assert.match(globalsSource,/\.change-menu\{position:fixed/);
  assert.match(globalsSource,/\.change-menu\{[^}]*z-index:1000/);
  assert.match(globalsSource,/\.delete-menu\{position:fixed/);
  assert.match(globalsSource,/\.delete-menu\{[^}]*z-index:1010/);
  assert.doesNotMatch(planViewSource,/window\.confirm/);
  assert.match(planViewSource,/className="delete-menu"/);
  assert.match(planViewSource,/createPortal\(\s*<div\s+className="change-menu"[\s\S]*?<\/div>,document\.body\s*\)/);
  assert.match(planViewSource,/createPortal\(<div className="delete-menu"[\s\S]*?<\/div>,document\.body\)/);
  assert.match(planViewSource,/viewBox="0 0 24 24"[^>]*><path d="M3 7h3c4 0 6 10 10 10h5"\/><path d="m18 14 3 3-3 3"\/><path d="M3 17h3c4 0 6-10 10-10h5"\/><path d="m18 4 3 3-3 3"\/>/);
  assert.match(globalsSource,/\.change-menu,\.delete-menu\{border-color:var\(--green\);background:var\(--green-soft\)\}/);
  assert.match(planViewSource,/className="change-menu-close"[\s\S]*onClick=\{closeChange\}/);
  assert.match(globalsSource,/\.change-menu-close\{position:absolute;top:10px;inset-inline-end:10px/);
  assert.match(planViewSource,/className="result-back-to-chat" onClick=\{returnToChat\}/);
  assert.match(planViewSource,/const returnToChat=\(\)=>window\.location\.assign\("\/"\)/);
  assert.doesNotMatch(planViewSource,/window\.history\.back\(\)/);
  assert.match(planViewSource,/className="result-ready card"[\s\S]*t\("aiFinished"\)[\s\S]*t\("itinerarySuggestionTitle"\)/);
  assert.match(globalsSource,/\.result-back-to-chat\{display:inline-flex/);
  assert.doesNotMatch(planViewSource,/quickActions\.map/);
  assert.doesNotMatch(planViewSource,/applyRefine\(prompt\)/);
  assert.doesNotMatch(planViewSource,/<article role="button"/);
  assert.match(planViewSource,/setTimeout\(\(\)=>controller\.abort\(\),30000\)/);
  assert.match(planViewSource,/"X-Session-Id":session,\.\.\.authHeader\(\)/);
  assert.match(planViewSource,/currentToken\.current!==requestToken/);
  assert.match(planViewSource,/const active=\(\)=>mounted\.current&&currentToken\.current===token/);
  assert.match(planViewSource,/if\(!active\(\)\)return/);
  for(const locale of locales){
    assert.equal(typeof workspace.workspaceTranslations[locale].regenerateSuccess,"string");
    assert.ok(workspace.workspaceTranslations[locale].regenerateSuccess.length>0);
  }
});

test("admin console exposes provider diagnostics without secrets",()=>{
  assert.match(adminPageSource,/provider_diagnostics/);
  assert.match(adminPageSource,/ai_quality/);
  assert.match(adminPageSource,/AI quality/);
  assert.match(adminPageSource,/api\/admin\/ai-quality/);
  assert.match(adminPageSource,/refreshAiQuality/);
  assert.match(adminPageSource,/copyAiLiveEnvSnippet/);
  assert.match(adminPageSource,/Copy \.env snippet/);
  assert.match(adminPageSource,/AI_MODE=groq/);
  assert.match(adminPageSource,/API_KEY_GROQ/);
  assert.match(adminPageSource,/llama-3\.3-70b-versatile/);
  assert.match(adminPageSource,/Refresh quality/);
  assert.match(adminPageSource,/fallback_rate_percent/);
  assert.match(adminPageSource,/fallback_plan_count/);
  assert.match(adminPageSource,/deterministic_rate_percent/);
  assert.match(adminPageSource,/deterministic_plan_count/);
  assert.match(adminPageSource,/AI deterministic/);
  assert.match(adminPageSource,/Operational limits/);
  assert.match(adminPageSource,/max_request_body_bytes/);
  assert.match(adminPageSource,/api\/admin\/providers\/diagnostics/);
  assert.match(adminPageSource,/required_env/);
  assert.match(adminPageSource,/next_action/);
  assert.match(adminPageSource,/circuit_breaker/);
  assert.match(adminPageSource,/circuit: \{item\.circuit_breaker\.state\}/);
  assert.match(adminPageSource,/api\/admin\/users/);
  assert.match(adminPageSource,/User management/);
  assert.match(adminPageSource,/maskUserId/);
  assert.match(adminPageSource,/api\/admin\/catalog\/export\.csv/);
  assert.match(adminPageSource,/api\/admin\/catalog\/quality/);
  assert.match(adminPageSource,/refreshCatalogQuality/);
  assert.match(adminPageSource,/Export CSV/);
  assert.match(adminPageSource,/URL\.createObjectURL\(blob\)/);
  assert.match(adminPageSource,/api\/admin\/ai-usage/);
  assert.match(adminPageSource,/AI usage/);
  assert.match(adminPageSource,/cost_usd\.toFixed\(6\)/);
  assert.match(adminPageSource,/api\/admin\/maintenance\/cleanup-expired/);
  assert.match(adminPageSource,/System maintenance/);
  assert.match(adminPageSource,/Cleanup expired plans/);
  assert.match(adminPageSource,/api\/admin\/events/);
  assert.match(adminPageSource,/Event audit log/);
  assert.match(adminPageSource,/JSON\.stringify\(event\.du_lieu\)\.slice\(0,180\)/);
  assert.doesNotMatch(adminPageSource,/api_key_length\}/);
});

test("history page uses durable session helper for list and mutation actions",()=>{
  assert.match(historyPageSource,/import \{ getSession \} from "@\/lib\/session"/);
  assert.match(historyPageSource,/const session = getSession\(\)/);
  assert.match(historyPageSource,/body:JSON\.stringify\(\{ma_phien:session\}\)/);
  assert.doesNotMatch(historyPageSource,/localStorage\.getItem\("ma_phien"\)/);
});

test("Vietnamese navigation labels the trip archive as history",()=>{
  assert.match(source,/vi:\{roadtrip:"Road trip",inventory:"Vé & lưu trú",trips:"Lịch sử"/);
  assert.match(navigationSource,/\["\/history", "trips"\]/);
});

test("history sidebar contains long plan titles without losing mobile scrolling",()=>{
  assert.match(historyPageSource,/className="history-plan-nav"[^]*plans\.map\(item => <Link[^]*<span>\{item\.ke_hoach\.tieu_de\}<\/span><span aria-hidden="true">/);
  assert.match(globalsSource,/\.history-page \.history-plan-nav>a\{[^}]*min-width:0;max-width:100%/);
  assert.match(globalsSource,/\.history-page \.history-plan-nav>a span:first-child\{[^}]*flex:1 1 auto;min-width:0;[^}]*text-overflow:ellipsis/);
  assert.match(globalsSource,/\.history-page \.history-plan-nav>a span:last-child\{\s*flex:0 0 auto;?\s*\}/);
  assert.match(globalsSource,/@media\(max-width:720px\)\{\.history-page \.history-plan-nav\{overflow-x:auto;?\}\.history-page \.history-plan-nav>a\{min-width:210px;max-width:210px;?\}\}/);
});

test("support queue actions guard duplicate state transitions",()=>{
  assert.match(supportPageSource,/const pendingRef = useRef<string\|null>\(null\)/);
  assert.match(supportPageSource,/if\(pendingRef\.current\) return/);
  assert.match(supportPageSource,/setPendingRequest\(item\.id\)/);
  assert.match(supportPageSource,/disabled=\{pendingRequest!==null\}/);
  assert.match(supportPageSource,/finally \{\s*pendingRef\.current=null; setPendingRequest\(null\);/);
});

test("invalid and corrupt preferences restore valid language direction",()=>{
  assert.equal(core.normalizeLocale("ar"),"ar");
  assert.equal(core.normalizeLocale("unsupported"),"vi");
  assert.equal(core.normalizeLocale(null),"vi");
  assert.match(source,/document\.documentElement\.lang=next/);
  assert.match(source,/document\.documentElement\.dir=\["ar","he"\]/);
  assert.match(source,/catch\{apply\("vi"\)\}/);
  assert.match(source,/event\.key===null/);
  assert.match(source,/addEventListener\("storage",sync\)/);
});

test("interpolation replaces template tokens once without rewriting values",()=>{
  assert.equal(core.interpolate("{first} {second}",{first:"{second}",second:"safe"}),"{second} safe");
  assert.equal(core.interpolate("Hello {name}",{}),"Hello {name}");
});

test("planner keeps its timeout, safe status and request contracts",()=>{
  assert.match(plannerSource,/setTimeout\(\(\) => controller\.abort\(\), 300000\)/);
  assert.match(nextConfigSource,/async rewrites\(\)/);
  assert.match(nextConfigSource,/proxyTimeout:\s*300000/);
  assert.match(nextConfigSource,/destination: `\$\{apiOrigin\}\/api\/:path\*`/);
  assert.match(nextConfigSource,/Array\.from\(\{ length: 11 \}/);
  assert.match(nextConfigSource,/http:\/\/localhost:\$\{8000 \+ index\}/);
  assert.match(nextConfigSource,/http:\/\/127\.0\.0\.1:\$\{8000 \+ index\}/);
  assert.match(nextConfigSource,/'unsafe-eval'/);
  assert.match(nextConfigSource,/font-src 'self' data:/);
  assert.match(plannerSource,/plan-generate-nonce/);
  assert.match(plannerSource,/requestNonce\(fingerprint\)/);
  assert.match(plannerSource,/clearNonce\(\);\s*setSession/);
  assert.match(plannerSource,/function inferDuration\(value: string\)/);
  assert.match(plannerSource,/function inferClockRange\(/);
  assert.match(plannerSource,/function inferHourSpan\(/);
  assert.match(plannerSource,/function inferDateRange\(/);
  assert.match(plannerSource,/ngay_di: ngayDi/);
  assert.match(plannerSource,/từ 20\/8 đến 22\/8/);
  assert.match(plannerSource,/setNeedsDuration\(true\)/);
  assert.match(plannerSource,/needsDuration &&/);
  assert.match(plannerSource,/const \[pendingContext, setPendingContext\]/);
  assert.match(plannerSource,/const \[needsDestination, setNeedsDestination\]/);
  assert.match(plannerSource,/const \[pendingDuration, setPendingDuration\]/);
  assert.match(plannerSource,/function hasDestination\(value: string\)/);
  assert.match(plannerSource,/function answerDestination\(answer: string\)/);
  assert.match(plannerSource,/function pickSuggestedDestination\(/);
  assert.match(plannerSource,/function applyPickedDestination\(/);
  assert.match(plannerSource,/THEME_DESTINATION_FALLBACKS/);
  assert.match(plannerSource,/Gợi ý cho tôi/);
  assert.match(plannerSource,/setNeedsDestination\(true\)/);
  assert.match(plannerSource,/needsDestination &&/);
  assert.match(plannerSource,/role="group" aria-label=\{t\("destinationPrompt"\)\}/);
  assert.match(plannerSource,/if \(!knownDestination && !hasDestination\(requestContext\)\) \{/);
  assert.match(plannerSource,/if \(!hasDestination\(answer\)\) \{/);
  assert.match(plannerSource,/const DEFAULT_LOCATION/);
  assert.match(plannerSource,/const DESTINATION_LOCATIONS/);
  assert.match(plannerSource,/function destinationLocation\(value: string\)/);
  assert.match(plannerSource,/pendingIntentLocation/);
  assert.match(plannerSource,/location: pendingIntentLocation\.current \?\? destinationLocation\(composedContext\)/);
  assert.match(plannerSource,/lat: 16\.0544, lng: 108\.2022/);
  assert.match(plannerSource,/continueOrAskPeople\(requestContext, duration, inferPairedPeople\(answer\)\)/);
  assert.match(plannerSource,/Hà Nội/);
  assert.match(plannerSource,/Hạ Long/);
  assert.match(plannerSource,/Đà Nẵng/);
  assert.match(plannerSource,/role="log" aria-live="polite"/);
  assert.match(plannerSource,/role="group" aria-label=\{t\("durationLabel"\)\}/);
  assert.match(plannerSource,/className="chat-composer"/);
  assert.match(plannerSource,/className="chat-box chat-input-shell"/);
  assert.match(plannerSource,/className="chat-input-icon" aria-hidden="true"/);
  assert.match(plannerSource,/className="chat-send"/);
  assert.match(plannerSource,/const \[needsPeople, setNeedsPeople\]/);
  assert.match(plannerSource,/function inferPeople\(value: string\)/);
  assert.match(plannerSource,/function inferDayCount\(value: string\)/);
  assert.match(plannerSource,/function inferPairedPeople\(value: string\)/);
  assert.match(plannerSource,/function composeRequestContext\(/);
  assert.match(plannerSource,/function peopleQuestion\(\)/);
  assert.match(plannerSource,/function answerPeople\(answer: string\)/);
  assert.match(plannerSource,/if \(needsPeople\) \{/);
  assert.match(plannerSource,/const bareNumber = normalized\.match/);
  assert.match(plannerSource,/if \(\!travelers\) \{/);
  assert.doesNotMatch(plannerSource,/id="planner-people"/);
  assert.doesNotMatch(plannerSource,/htmlFor="planner-people"/);
  assert.match(globalsSource,/\.planner \.chat-input-shell\{[^}]*border-radius:999px/);
  assert.match(globalsSource,/\.planner \.chat-send\{[^}]*border-radius:50%/);
  assert.match(plannerSource,/transcriptEnd\.current\?\.scrollIntoView/);
  assert.match(plannerSource,/if \(needsDuration\) \{/);
  assert.match(plannerSource,/if \(!duration\) \{/);
  assert.match(plannerSource,/const requestContext = `\$\{pendingContext\.trim\(\)\}\\n\$\{answer\.trim\(\)\}`/);
  assert.match(plannerSource,/continueOrAskPeople\(requestContext, duration, inferPairedPeople\(answer\)\)/);
  assert.match(plannerSource,/lastRequest\.current = \{ context: composedContext, duration, people: travelers \}/);
  assert.doesNotMatch(plannerSource,/chat-prompt-chips/);
  assert.match(plannerSource,/onClick=\{retryGenerate\}/);
  for(const duration of ["vai_gio","nua_ngay","ca_ngay","nhieu_ngay"]) assert.match(plannerSource,new RegExp(`\\[\\"[^\\"]+\\", \\"${duration}\\"\\]`));
  assert.match(plannerSource,/t\("durationLabel"\)/);
  assert.doesNotMatch(plannerSource,/Bạn muốn đi trong bao lâu/);
  assert.doesNotMatch(plannerSource,/id="planner-duration"/);
  assert.match(plannerSource,/cause instanceof DOMException && cause\.name === "AbortError"/);
  assert.match(plannerSource,/setErrorKey\("generateFailed"\)/);
  assert.match(plannerSource,/setErrorDetail/);
  assert.match(plannerSource,/thoi_luong: duration/);
  assert.match(plannerSource,/Vì bạn yêu cầu lên kế hoạch nhiều ngày nên hệ thống sẽ mất vài phút để tạo lịch trình/);
  assert.match(plannerSource,/tối đa 30 ngày mỗi chặng/);
  assert.match(plannerSource,/waitNotice \?\? t\(statusKey\)/);
  assert.match(plannerSource,/if \(overflowNotice\) addMessage\("assistant", overflowNotice\)/);
  assert.doesNotMatch(plannerSource,/addMessage\("assistant", longTripWait\)/);
  const backendStatuses=[...backendPlanSource.matchAll(/sse\("status", \{"status": "([a-z_]+)"\}\)/g)].map(match=>match[1]);
  assert.deepEqual(backendStatuses,["finding_places","long_trip_wait","routing_plan"]);
  for(const status of backendStatuses)assert.match(plannerSource,new RegExp(`value\\s*===\\s*"${status}"`),`missing localized mapping for ${status}`);
  assert.doesNotMatch(plannerSource,/setError\([^)]*\.message/);
});

test("planner keeps Đà Lạt after a healing suggestion and treats 3 as 3 days",()=>{
  assert.match(plannerSource,/function normalizeText\(value: string\)/);
  assert.match(plannerSource,/\.replace\(\/\[đĐ\]\/g, "d"\)/);
  assert.match(plannerSource,/hasDestination\(pendingContext\) \|\| pendingIntentLocation\.current != null/);
  assert.match(plannerSource,/function durationContextLine\(/);
  assert.match(plannerSource,/`\$\{days\} ngày`/);
  assert.match(plannerSource,/setPendingContext\(requestContext\);\s*setPendingDuration\(duration\);/);
  const fold=(value)=>value.normalize("NFD").replace(/[\u0300-\u036f]/g,"").replace(/[đĐ]/g,"d").toLowerCase();
  const daLat=/\b(da lat|dalat|lam dong)\b/;
  const daNang=/\b(da nang|danang)\b/;
  assert.equal(daLat.test(fold("Đà Lạt")),true);
  assert.equal(daNang.test(fold("Đà Nẵng")),true);
  assert.equal(daLat.test(fold("tôi muốn đi chữa lành\nĐà Lạt\n3")),true);
});

test("SSE parser accepts CRLF and guards malformed or duplicate events",()=>{
  assert.match(apiSource,/split\(\/\\r\?\\n\\r\?\\n\/\)/);
  assert.match(apiSource,/done && buffer\.trim\(\)/);
  assert.match(apiSource,/typeof data\.status !== "string"/);
  assert.match(apiSource,/if \(result\) throw new Error\("Duplicate result event"\)/);
});

test("SSE parser returns a CRLF result without waiting for stream close",async()=>{
  const encoder=new TextEncoder();
  let cancelled=false;
  const stream=new ReadableStream({start(controller){controller.enqueue(encoder.encode('event: status\r\ndata: {"status":"working"}\r\n\r\nevent: result\r\ndata: {"token":"safe","ma_phien":"session","plan":{},"phien_ban":1}\r\n\r\n'))},cancel(){cancelled=true}});
  const statuses=[];
  const result=await api.consumePlanStream(new Response(stream),value=>statuses.push(value));
  assert.equal(result.token,"safe");assert.deepEqual(statuses,["working"]);assert.equal(cancelled,true);
});
