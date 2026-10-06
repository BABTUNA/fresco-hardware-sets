# distinct sample books for experiments, (project, file, first page, last page) 0-indexed inclusive
BOOKS = {
    "gerrard":   ("2353-gerrard-street-shelter", "Hdw Spec & Sch-IFT_5.pdf", 0, 35),
    "oswego":    ("village-of-oswego", "SPECIFICATIONS VOLUME 1.pdf", 416, 445),
    "roselle":   ("roselle-public-library", "087100_FL_-_Door_Hardware_IFB_REVISED.pdf", 14, 16),
    "bridgeport":("81-85-bridgeport", "08-70-00-Hardware-Schedule.pdf", 0, 48),
    "jcryan":    ("jc-ryan-2", "087100 - Door Hardware-6.pdf", 20, 45),
    "star":      ("star-hardware", "9839d1a1-Division_8_Specs_-_Commons_Lane.pdf", 60, 112),
    "valor":     ("valor-acres-building-e", "087100-DOOR-HARDWARE_Rev_2.pdf", 0, 17),
    "morris":    ("morris-bank", "030f2d1d-Morris_Bank_Macon_-Spec_Manual_Issued_for_Const._1-26-26_FULL_SPECS.pdf", 270, 330),
    "ami":       ("ami", "c43c36d9-000_Full_Volume_ATC_Renovation_Bid_Specs_Volume_1__1_.pdf", 395, 425),
    "hfh":       ("hfh-dg-hospital", "08 71 00 - DOOR HARDWARE.pdf", 2, 183),
    "lyons":     ("lyons-township-hs", "Project Manual (1).pdf", 280, 308),
    "marketview":("market-view-apartments", "S_251107 Market View Prelim Project Manual_pdf.pdf", 760, 795),
    "national":  ("national-doors-and-hardware", "15e2b8ac-FS17_Specs_V1.pdf", 400, 430),
    "sat":       ("sat-tdp", "2025.12.19 - SAT TDP - Project Manual.pdf", 700, 830),
    "doorco":    ("the-door-company", "Vantage TX-22 Div 01, 08.pdf", 400, 470),
    "shubie":    ("shubie-center", "e2231795-IFT_Specs.pdf", 172, 200),
    "usi":       ("usi", "c9634958-Radnet_Building_-_Specs.pdf", 560, 575),
    "livelle":   ("livelle-mulholland", "2025-12-12_Livelle_Bid_Set_Project_Manual_Vol1_rev1.pdf", 630, 665),
}
def path(name):
    p, f, *_ = BOOKS[name]
    import os
    return os.path.join(os.path.dirname(__file__), "..", "data", p, f)
