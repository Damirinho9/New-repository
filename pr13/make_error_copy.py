from docx import Document
import json

src = "PR13_Roslavl_3pages.docx"
out = "PR13_1_source.docx"

corrections = [
 {"paragraph":1,"type":"орфографическая","correct":"древнейших","wrong":"древнейшых"},
 {"paragraph":1,"type":"грамматическая","correct":"Он расположен","wrong":"Он расположена"},
 {"paragraph":1,"type":"пунктуационная","correct":"Смоленской области, на левом","wrong":"Смоленской области на левом"},
 {"paragraph":1,"type":"стилистическая","correct":"важное положение","wrong":"важное и значимое положение"},
 {"paragraph":2,"type":"орфографическая","correct":"Литовского","wrong":"Литовсково"},
 {"paragraph":2,"type":"грамматическая","correct":"город был занят","wrong":"город были занят"},
 {"paragraph":2,"type":"пунктуационная","correct":"русскими войсками, а по условиям","wrong":"русскими войсками а по условиям"},
 {"paragraph":2,"type":"стилистическая","correct":"власть над Рославлем вновь менялась","wrong":"власть над Рославлем вновь снова менялась"},
 {"paragraph":3,"type":"орфографическая","correct":"перепланировка","wrong":"перепланеровка"},
 {"paragraph":3,"type":"грамматическая","correct":"Эти постройки во многом сформировали","wrong":"Эти постройки во многом сформировал"},
 {"paragraph":3,"type":"пунктуационная","correct":"После административных преобразований город стал","wrong":"После административных преобразований город, стал"},
 {"paragraph":3,"type":"стилистическая","correct":"каменные административные здания","wrong":"различные разные каменные административные здания"},
 {"paragraph":4,"type":"орфографическая","correct":"железнодорожное движение","wrong":"железнодорожнае движение"},
 {"paragraph":4,"type":"грамматическая","correct":"мастерские, которые со временем стали","wrong":"мастерские, который со временем стали"},
 {"paragraph":4,"type":"пунктуационная","correct":"французскими мародерами, а в сентябре","wrong":"французскими мародерами а в сентябре"},
 {"paragraph":4,"type":"стилистическая","correct":"Особенно заметные изменения","wrong":"Особенно очень заметные изменения"},
 {"paragraph":5,"type":"орфографическая","correct":"наступательной операции","wrong":"наступатильной операции"},
 {"paragraph":5,"type":"грамматическая","correct":"погибли десятки тысяч людей","wrong":"погибло десятки тысяч людей"},
 {"paragraph":5,"type":"пунктуационная","correct":"расширяться: в 1931 году","wrong":"расширяться в 1931 году"},
 {"paragraph":5,"type":"стилистическая","correct":"Самым тяжелым периодом","wrong":"Самым наиболее тяжелым периодом"},
 {"paragraph":6,"type":"орфографическая","correct":"археологические находки","wrong":"археологичиские находки"},
 {"paragraph":6,"type":"грамматическая","correct":"город переживал войны","wrong":"город переживали войны"},
 {"paragraph":6,"type":"пунктуационная","correct":"В 1970 году Рославль","wrong":"В 1970 году, Рославль"},
 {"paragraph":6,"type":"стилистическая","correct":"Современный город сохраняет","wrong":"Современный город в настоящее время сегодня сохраняет"}
]

doc = Document(src)
for item in corrections:
    wrong, repl = item["correct"], item["wrong"]
    found = False
    for p in doc.paragraphs:
        for r in p.runs:
            if wrong in r.text:
                r.text = r.text.replace(wrong, repl, 1)
                found = True
                break
        if found:
            break
    if not found:
        raise RuntimeError(f"not found: {wrong!r}")
doc.save(out)
with open("corrections.json","w",encoding="utf-8") as f:
    json.dump(corrections,f,ensure_ascii=False,indent=2)
print("ERROR_COPY_CREATED=24")
