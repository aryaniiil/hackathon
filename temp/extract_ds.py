from datasets import load_dataset

ds = load_dataset("fazni/role-based-on-skills-2.0")

print(ds)

with open("skills_dataset.txt", "w", encoding="utf-8") as f:
    for row in ds["train"]:
        f.write(str(row) + "\n")