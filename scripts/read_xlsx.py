import openpyxl, sys, glob

path = glob.glob("*.xlsx")[0]
wb = openpyxl.load_workbook(path, data_only=True)
with open("scripts/out.txt", "w", encoding="utf-8") as f:
    for ws in wb.worksheets:
        f.write(f"=== SHEET: {ws.title} dims: {ws.dimensions} ===\n")
        for row in ws.iter_rows(values_only=True):
            if any(c is not None for c in row):
                f.write(str(row) + "\n")
