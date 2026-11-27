# 재정 고속국도 선형: assign.py → build.py를 한 인터프리터에서 차례로 돌린다.
# build.py는 assign.py가 만든 변수(ways, state, hav, CX, CY 등)를 그대로 쓴다.
import os
here = os.path.dirname(os.path.abspath(__file__))
g = {"__name__": "__main__"}
for n in ("assign.py", "build.py"):
    g["__file__"] = os.path.join(here, n)
    exec(compile(open(g["__file__"], encoding="utf-8").read(), g["__file__"], "exec"), g)
