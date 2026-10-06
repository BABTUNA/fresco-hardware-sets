# end-to-end prep: finder picks pages, we write dumps for the spec writer and render new ground-truth pages
import json, os, random
import pdfplumber
from finder import page_scores, runs
from spec_parse import dump

D = "../data/"
E2E = {
    "gerrard": "2353-gerrard-street-shelter/Hdw Spec & Sch-IFT_5.pdf",
    "bridgeport": "81-85-bridgeport/08-70-00-Hardware-Schedule.pdf",
    "ami": "ami/c43c36d9-000_Full_Volume_ATC_Renovation_Bid_Specs_Volume_1__1_.pdf",
    "forest": "forest-park-school/Project Manual (1).pdf",
    "hfh": "hfh-dg-hospital/08 71 00 - DOOR HARDWARE.pdf",
    "jcryan": "jc-ryan-2/087100 - Door Hardware-6.pdf",
    "livelle": "livelle-mulholland/2025-12-12_Livelle_Bid_Set_Project_Manual_Vol1_rev1.pdf",
    "lyons": "lyons-township-hs/Project Manual (1).pdf",
    "marketview": "market-view-apartments/S_251107 Market View Prelim Project Manual_pdf.pdf",
    "morris": "morris-bank/030f2d1d-Morris_Bank_Macon_-Spec_Manual_Issued_for_Const._1-26-26_FULL_SPECS.pdf",
    "national": "national-doors-and-hardware/15e2b8ac-FS17_Specs_V1.pdf",
    "roselle": "roselle-public-library/087100_FL_-_Door_Hardware_IFB_REVISED.pdf",
    "sat": "sat-tdp/2025.12.19 - SAT TDP - Project Manual.pdf",
    "shubie": "shubie-center/e2231795-IFT_Specs.pdf",
    "sjc": "sjc-well-behavioral/89671ede-20260218_SJC_BeWell_Bldg_B_85__DESIGN_UPDATE_-_SPECIFICATIONS.pdf",
    "star": "star-hardware/9839d1a1-Division_8_Specs_-_Commons_Lane.pdf",
    "doorco": "the-door-company/Vantage TX-22 Div 01, 08.pdf",
    "usi": "usi/c9634958-Radnet_Building_-_Specs.pdf",
    "valor": "valor-acres-building-e/087100-DOOR-HARDWARE_Rev_2.pdf",
    "oswego": "village-of-oswego/SPECIFICATIONS VOLUME 1.pdf",
}
NEW_GT = ["gerrard", "oswego", "star", "bridgeport", "ami", "lyons", "marketview", "national", "shubie", "forest", "sjc"]
random.seed(11)
os.makedirs("dumps_e2e", exist_ok=True)
plan = {}
for name, rel in E2E.items():
    s, v = page_scores(D + rel)
    r = runs(s, v)
    pages = [p for a, b in r for p in range(a, b + 1)]
    dump_pages = sorted(sorted(pages, key=lambda p: s[p], reverse=True)[:2])
    pdf = pdfplumber.open(D + rel)
    open(f"dumps_e2e/{name}.txt", "w").write(dump(pdf, dump_pages))
    gt_pages = []
    if name in NEW_GT:
        pool = [p for p in pages if p not in dump_pages and s[p] >= 3] or dump_pages
        gt_pages = sorted(random.sample(pool, min(2, len(pool))))
        for p in gt_pages:
            pdf.pages[p].to_image(resolution=130).save(f"eval/pages/{name}_p{p}.png")
    plan[name] = {"file": rel, "runs": r, "dump_pages": dump_pages, "gt_pages": gt_pages}
    print(name, plan[name]["runs"], "dump", dump_pages, "gt", gt_pages, flush=True)
json.dump(plan, open("eval/e2e_plan.json", "w"), indent=1)
