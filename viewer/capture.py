from playwright.sync_api import sync_playwright
import time, json, os, traceback

BASE = "http://127.0.0.1:8000/viewer"
VIEWS = [("sch",150), ("pcb",90), ("3d",90)]
os.makedirs("viewer_out", exist_ok=True)

def dump_state(page, name):
    data={"url":page.url,"title":page.title(),"frames":[]}
    for i,f in enumerate(page.frames):
        item={"i":i,"url":f.url,"name":f.name}
        try:
            item["text"]=f.locator("body").inner_text(timeout=5000)[:12000]
        except Exception as e:
            item["text_error"]=str(e)
        try:
            item["buttons"]=f.locator("button").all_inner_texts()[:100]
        except Exception as e:
            item["buttons_error"]=str(e)
        data["frames"].append(item)
    with open(f"viewer_out/{name}_state.json","w",encoding="utf-8") as fp:
        json.dump(data,fp,ensure_ascii=False,indent=2)

with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,args=["--disable-dev-shm-usage","--no-sandbox","--use-gl=swiftshader"])
    context=browser.new_context(viewport={"width":1440,"height":1000}, device_scale_factor=1)
    page=context.new_page()
    page.on("console", lambda msg: print("CONSOLE", msg.type, msg.text))
    page.on("pageerror", lambda exc: print("PAGEERROR", exc))
    page.on("requestfailed", lambda req: print("REQFAIL", req.url, req.failure))
    for name, wait_s in VIEWS:
        try:
            url=f"{BASE}/{name}.html?ts={int(time.time())}"
            print("OPEN",url,flush=True)
            page.goto(url,wait_until="domcontentloaded",timeout=120000)
            try:
                page.wait_for_selector("iframe",timeout=120000)
                print("IFRAME FOUND",name,flush=True)
            except Exception as e:
                print("NO IFRAME YET",name,e,flush=True)
            checkpoints=[30,60,90,120,150]
            elapsed=0
            for target in checkpoints:
                if target>wait_s: break
                time.sleep(target-elapsed); elapsed=target
                page.screenshot(path=f"viewer_out/{name}_{target:03d}s_page.png",full_page=True)
                dump_state(page,f"{name}_{target:03d}s")
                print("CHECKPOINT",name,target,flush=True)
            if elapsed<wait_s: time.sleep(wait_s-elapsed)
            page.screenshot(path=f"viewer_out/{name}_final_page.png",full_page=True)
            iframe=page.locator("iframe").first
            if iframe.count():
                iframe.screenshot(path=f"viewer_out/{name}_final_viewer.png")
            dump_state(page,f"{name}_final")
        except Exception as e:
            print("VIEW ERROR",name,repr(e),flush=True)
            traceback.print_exc()
            try: page.screenshot(path=f"viewer_out/{name}_error.png",full_page=True)
            except: pass
    browser.close()
