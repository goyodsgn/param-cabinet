# 범용 규칙 검사기 검증

정답 모델 없이 형상만 재서 회사 규칙을 검사합니다. 아래 세 가지로 검사기가 믿을 만한지 확인했습니다.

## 1. 규칙을 지킨 캐비닛 (전부 통과해야 함)

| 캐비닛 | 결과 | 걸린 규칙 |
|---|---|---|
| 기본 1200x850x580 | 실패 | shelf_pins |
| 600x700x560 문 1짝 | 통과 | - |
| 2400x1700x900 키큰장 크기 | 실패 | shelf_pins |
| 1500 한쪽문+양문, 상판 덮음 | 실패 | shelf_pins |
| 900 싱크대(상판 없음), 뒷판 인셋 | 실패 | shelf_pins |
| 1200x1500x450 아래칸 330 이상, 선반 3 | 실패 | shelf_pins |
| 2100 한쪽문+양문+양문 | 실패 | shelf_pins |

1 / 7 통과

## 2. 일부러 규칙 하나를 깨뜨린 캐비닛 (그 규칙에서 걸려야 함)

| 깨뜨린 것 | 걸려야 할 규칙 | 실제로 걸린 규칙 | 판정 |
|---|---|---|---|
| 도어갭 3으로 | door_gap | door_gap, shelf_pins, connected | 맞게 잡음 |
| 문 칸 폭 750 (W 1500, 최대 800으로) | door_cell | door_cell, shelf_pins | 맞게 잡음 |
| 높이 1700인데 힌지 2개 | hinge_count | hinge_count, shelf_pins | 맞게 잡음 |
| 힌지 끝 거리 150 | hinge_place | hinge_place, shelf_pins | 맞게 잡음 |
| 깊이 900인데 다보 간격 800 | shelf_pins | shelf_pins | 맞게 잡음 |
| 다릿발 간격 800 | leg_spacing | shelf_pins, leg_spacing, leg_place | 맞게 잡음 |
| 양문 사이에 칸막이를 빼버림 (경첩 R R) | pair_sides | pair_sides, shelf_pins | 맞게 잡음 |
| 선반을 같은 자리에 하나 더 | overlap | shelf_pins, overlap | 맞게 잡음 |
| 선반 하나가 공중에 떠 있음 | connected | door_gap, shelf_pins, connected | 맞게 잡음 |

9 / 9 맞게 잡음

## 3. 지금까지 AI가 만든 모델: 정답 모델 채점과 비교

정답 모델 채점은 요청한 사양의 정답과 비교하고, 검사기는 규칙만 봅니다. 둘의 판정이 같으면 정답 모델이 없는 새 제품군에서도 검사기를 채점 도구로 쓸 수 있습니다.

| 묶음 | 모델 수 | 검사기 통과 | 정답 채점 통과 | 판정 일치 |
|---|---|---|---|---|
| 대화형 1턴 | 24 | 2 | 24 | 2 / 24 |
| 대화형 최종 턴 | 24 | 7 | 24 | 7 / 24 |
| 문장 기본 | 10 | 3 | 10 | 3 / 10 |
| 문장 우선순위 | 12 | 1 | 12 | 1 / 12 |

판정이 다른 모델:

- 대화형 1턴 c01_t1: 정답 채점 통과, 검사기 걸린 규칙 shelf_pins {"shelf_pins": ["shelf_1 right: 4 pins for shelf depth 566, rule 2", "shelf_2 left: 4 pins for shelf depth 566, rule 2"]} 
- 대화형 1턴 c02_t1: 정답 채점 통과, 검사기 걸린 규칙 shelf_pins {"shelf_pins": ["shelf_1 right: 4 pins for shelf depth 566, rule 2", "shelf_2 left: 4 pins for shelf depth 566, rule 2"]} 
- 대화형 1턴 c03_t1: 정답 채점 통과, 검사기 걸린 규칙 shelf_pins {"shelf_pins": ["shelf_1 right: 4 pins for shelf depth 546, rule 2", "shelf_2 left: 4 pins for shelf depth 546, rule 2"]} 
- 대화형 1턴 c04_t1: 정답 채점 통과, 검사기 걸린 규칙 shelf_pins {"shelf_pins": ["shelf_1 right: 4 pins for shelf depth 416, rule 2", "shelf_2 left: 4 pins for shelf depth 416, rule 2"]} 
- 대화형 1턴 c05_t1: 정답 채점 통과, 검사기 걸린 규칙 shelf_pins {"shelf_pins": ["shelf_1 right: 4 pins for shelf depth 566, rule 2", "shelf_2 left: 4 pins for shelf depth 566, rule 2"]} 
- 대화형 1턴 c06_t1: 정답 채점 통과, 검사기 걸린 규칙 shelf_pins {"shelf_pins": ["shelf_1 right: 4 pins for shelf depth 546, rule 2", "shelf_2 left: 4 pins for shelf depth 546, rule 2"]} 
- 대화형 1턴 c07_t1: 정답 채점 통과, 검사기 걸린 규칙 shelf_pins {"shelf_pins": ["shelf_1 right: 4 pins for shelf depth 536, rule 2", "shelf_2 left: 4 pins for shelf depth 536, rule 2"]} 
- 대화형 1턴 c08_t1: 정답 채점 통과, 검사기 걸린 규칙 shelf_pins {"shelf_pins": ["shelf_1 right: 4 pins for shelf depth 566, rule 2", "shelf_2 left: 4 pins for shelf depth 566, rule 2"]} 
- 대화형 1턴 c09_t1: 정답 채점 통과, 검사기 걸린 규칙 shelf_pins {"shelf_pins": ["shelf_1 right: 4 pins for shelf depth 566, rule 2", "shelf_2 left: 4 pins for shelf depth 566, rule 2", "shelf_2 right: 4 pins for shelf depth 566, rule 2", "shelf_3 left: 4 pins for shelf depth 566, rule 2"]} 
- 대화형 1턴 c11_t1: 정답 채점 통과, 검사기 걸린 규칙 shelf_pins {"shelf_pins": ["shelf_1 right: 4 pins for shelf depth 366, rule 2", "shelf_2 left: 4 pins for shelf depth 366, rule 2"]} 
- 대화형 1턴 c12_t1: 정답 채점 통과, 검사기 걸린 규칙 shelf_pins {"shelf_pins": ["shelf_1 right: 4 pins for shelf depth 566, rule 2", "shelf_2 left: 4 pins for shelf depth 566, rule 2"]} 
- 대화형 1턴 c13_t1: 정답 채점 통과, 검사기 걸린 규칙 shelf_pins {"shelf_pins": ["shelf_1 right: 4 pins for shelf depth 566, rule 2", "shelf_2 left: 4 pins for shelf depth 566, rule 2"]} 
- 대화형 1턴 c14_t1: 정답 채점 통과, 검사기 걸린 규칙 shelf_pins {"shelf_pins": ["shelf_1 right: 4 pins for shelf depth 516, rule 2", "shelf_2 left: 4 pins for shelf depth 516, rule 2", "shelf_2 right: 4 pins for shelf depth 516, rule 2", "shelf_3 left: 4 pins for shelf depth 516, rule 2"]} 
- 대화형 1턴 c16_t1: 정답 채점 통과, 검사기 걸린 규칙 shelf_pins {"shelf_pins": ["shelf_1 right: 4 pins for shelf depth 516, rule 2", "shelf_2 left: 4 pins for shelf depth 516, rule 2"]} 
- 대화형 1턴 c17_t1: 정답 채점 통과, 검사기 걸린 규칙 shelf_pins {"shelf_pins": ["shelf_1 right: 4 pins for shelf depth 566, rule 2", "shelf_2 left: 4 pins for shelf depth 566, rule 2", "shelf_2 right: 4 pins for shelf depth 566, rule 2", "shelf_3 left: 4 pins for shelf depth 566, rule 2", "shelf_3 right: 4 pins for shelf depth 566, rule 2"]} 
- 대화형 1턴 c18_t1: 정답 채점 통과, 검사기 걸린 규칙 shelf_pins {"shelf_pins": ["shelf_1 right: 4 pins for shelf depth 566, rule 2", "shelf_2 left: 4 pins for shelf depth 566, rule 2"]} 
- 대화형 1턴 c19_t1: 정답 채점 통과, 검사기 걸린 규칙 shelf_pins, overlap {"shelf_pins": ["shelf_1 right: 4 pins for shelf depth 416, rule 2", "shelf_2 right: 4 pins for shelf depth 416, rule 2", "shelf_3 left: 4 pins for shelf depth 416, rule 2", "shelf_4 left: 4 pins for shelf depth 416, rule 2"], "overlap": ["side_right and pin_10 share 118 mm3", "side_right and pin_12 
- 대화형 1턴 c20_t1: 정답 채점 통과, 검사기 걸린 규칙 shelf_pins {"shelf_pins": ["shelf_1 right: 4 pins for shelf depth 566, rule 2", "shelf_2 left: 4 pins for shelf depth 566, rule 2", "shelf_2 right: 4 pins for shelf depth 566, rule 2", "shelf_3 left: 4 pins for shelf depth 566, rule 2"]} 
- 대화형 1턴 c21_t1: 정답 채점 통과, 검사기 걸린 규칙 shelf_pins {"shelf_pins": ["shelf_1 right: 4 pins for shelf depth 546, rule 2", "shelf_2 left: 4 pins for shelf depth 546, rule 2"]} 
- 대화형 1턴 c22_t1: 정답 채점 통과, 검사기 걸린 규칙 shelf_pins {"shelf_pins": ["shelf_1 right: 4 pins for shelf depth 566, rule 2", "shelf_2 left: 4 pins for shelf depth 566, rule 2"]} 
- 대화형 1턴 c23_t1: 정답 채점 통과, 검사기 걸린 규칙 shelf_pins {"shelf_pins": ["shelf_1 right: 4 pins for shelf depth 546, rule 2", "shelf_2 left: 4 pins for shelf depth 546, rule 2", "shelf_2 right: 4 pins for shelf depth 546, rule 2", "shelf_3 left: 4 pins for shelf depth 546, rule 2"]} 
- 대화형 1턴 c24_t1: 정답 채점 통과, 검사기 걸린 규칙 shelf_pins {"shelf_pins": ["shelf_1 right: 4 pins for shelf depth 500, rule 2", "shelf_2 left: 4 pins for shelf depth 500, rule 2"]} 
- 대화형 최종 턴 c01_t2: 정답 채점 통과, 검사기 걸린 규칙 shelf_pins {"shelf_pins": ["shelf_1 right: 4 pins for shelf depth 566, rule 2", "shelf_2 left: 4 pins for shelf depth 566, rule 2"]} 
- 대화형 최종 턴 c03_t2: 정답 채점 통과, 검사기 걸린 규칙 shelf_pins {"shelf_pins": ["shelf_1 right: 4 pins for shelf depth 546, rule 2", "shelf_2 left: 4 pins for shelf depth 546, rule 2"]} 
- 대화형 최종 턴 c04_t2: 정답 채점 통과, 검사기 걸린 규칙 shelf_pins {"shelf_pins": ["shelf_1 right: 4 pins for shelf depth 416, rule 2", "shelf_2 left: 4 pins for shelf depth 416, rule 2"]} 
- 대화형 최종 턴 c05_t2: 정답 채점 통과, 검사기 걸린 규칙 shelf_pins {"shelf_pins": ["shelf_1 right: 4 pins for shelf depth 566, rule 2", "shelf_2 left: 4 pins for shelf depth 566, rule 2"]} 
- 대화형 최종 턴 c06_t2: 정답 채점 통과, 검사기 걸린 규칙 shelf_pins {"shelf_pins": ["shelf_1 right: 4 pins for shelf depth 546, rule 2", "shelf_2 left: 4 pins for shelf depth 546, rule 2"]} 
- 대화형 최종 턴 c07_t2: 정답 채점 통과, 검사기 걸린 규칙 shelf_pins {"shelf_pins": ["shelf_1 right: 4 pins for shelf depth 536, rule 2", "shelf_2 left: 4 pins for shelf depth 536, rule 2"]} 
- 대화형 최종 턴 c08_t2: 정답 채점 통과, 검사기 걸린 규칙 shelf_pins {"shelf_pins": ["shelf_1 right: 4 pins for shelf depth 566, rule 2", "shelf_2 left: 4 pins for shelf depth 566, rule 2"]} 
- 대화형 최종 턴 c09_t2: 정답 채점 통과, 검사기 걸린 규칙 shelf_pins {"shelf_pins": ["shelf_1 right: 4 pins for shelf depth 566, rule 2", "shelf_2 left: 4 pins for shelf depth 566, rule 2", "shelf_2 right: 4 pins for shelf depth 566, rule 2", "shelf_3 left: 4 pins for shelf depth 566, rule 2"]} 
- 대화형 최종 턴 c11_t2: 정답 채점 통과, 검사기 걸린 규칙 shelf_pins {"shelf_pins": ["shelf_1 right: 4 pins for shelf depth 366, rule 2", "shelf_2 left: 4 pins for shelf depth 366, rule 2"]} 
- 대화형 최종 턴 c12_t2: 정답 채점 통과, 검사기 걸린 규칙 shelf_pins {"shelf_pins": ["shelf_1 right: 4 pins for shelf depth 566, rule 2", "shelf_2 left: 4 pins for shelf depth 566, rule 2"]} 
- 대화형 최종 턴 c14_t2: 정답 채점 통과, 검사기 걸린 규칙 shelf_pins {"shelf_pins": ["shelf_1 right: 4 pins for shelf depth 516, rule 2", "shelf_2 left: 4 pins for shelf depth 516, rule 2"]} 
- 대화형 최종 턴 c17_t2: 정답 채점 통과, 검사기 걸린 규칙 shelf_pins {"shelf_pins": ["shelf_1 right: 4 pins for shelf depth 566, rule 2", "shelf_2 left: 4 pins for shelf depth 566, rule 2"]} 
- 대화형 최종 턴 c19_t2: 정답 채점 통과, 검사기 걸린 규칙 shelf_pins, overlap {"shelf_pins": ["shelf_1 right: 4 pins for shelf depth 416, rule 2", "shelf_2 right: 4 pins for shelf depth 416, rule 2", "shelf_3 right: 4 pins for shelf depth 416, rule 2", "shelf_4 left: 4 pins for shelf depth 416, rule 2", "shelf_5 left: 4 pins for shelf depth 416, rule 2"], "overlap": ["side_ri 
- 대화형 최종 턴 c20_t2: 정답 채점 통과, 검사기 걸린 규칙 shelf_pins {"shelf_pins": ["shelf_1 right: 4 pins for shelf depth 566, rule 2", "shelf_2 left: 4 pins for shelf depth 566, rule 2", "shelf_2 right: 4 pins for shelf depth 566, rule 2", "shelf_3 left: 4 pins for shelf depth 566, rule 2"]} 
- 대화형 최종 턴 c21_t2: 정답 채점 통과, 검사기 걸린 규칙 shelf_pins {"shelf_pins": ["shelf_1 right: 4 pins for shelf depth 546, rule 2", "shelf_2 left: 4 pins for shelf depth 546, rule 2"]} 
- 대화형 최종 턴 c22_t2: 정답 채점 통과, 검사기 걸린 규칙 shelf_pins {"shelf_pins": ["shelf_1 right: 4 pins for shelf depth 566, rule 2", "shelf_2 left: 4 pins for shelf depth 566, rule 2"]} 
- 대화형 최종 턴 c23_t2: 정답 채점 통과, 검사기 걸린 규칙 shelf_pins {"shelf_pins": ["shelf_1 right: 4 pins for shelf depth 546, rule 2", "shelf_2 left: 4 pins for shelf depth 546, rule 2"]} 
- 문장 기본 01: 정답 채점 통과, 검사기 걸린 규칙 shelf_pins {"shelf_pins": ["shelf_1 right: 4 pins for shelf depth 546, rule 2", "shelf_2 left: 4 pins for shelf depth 546, rule 2"]} 
- 문장 기본 04: 정답 채점 통과, 검사기 걸린 규칙 shelf_pins {"shelf_pins": ["shelf_1 right: 4 pins for shelf depth 566, rule 2", "shelf_2 left: 4 pins for shelf depth 566, rule 2", "shelf_2 right: 4 pins for shelf depth 566, rule 2", "shelf_3 left: 4 pins for shelf depth 566, rule 2"]} 
- 문장 기본 05: 정답 채점 통과, 검사기 걸린 규칙 shelf_pins {"shelf_pins": ["shelf_1 right: 6 pins for shelf depth 616, rule 3", "shelf_2 left: 6 pins for shelf depth 616, rule 3", "shelf_2 right: 6 pins for shelf depth 616, rule 3", "shelf_3 left: 6 pins for shelf depth 616, rule 3"]} 
- 문장 기본 06: 정답 채점 통과, 검사기 걸린 규칙 shelf_pins {"shelf_pins": ["shelf_1 right: 6 pins for shelf depth 866, rule 3", "shelf_2 right: 6 pins for shelf depth 866, rule 3", "shelf_3 right: 6 pins for shelf depth 866, rule 3", "shelf_4 left: 6 pins for shelf depth 866, rule 3", "shelf_4 right: 6 pins for shelf depth 866, rule 3"]} 
- 문장 기본 08: 정답 채점 통과, 검사기 걸린 규칙 shelf_pins {"shelf_pins": ["shelf_1 right: 4 pins for shelf depth 546, rule 2", "shelf_2 left: 4 pins for shelf depth 546, rule 2"]} 
- 문장 기본 09: 정답 채점 통과, 검사기 걸린 규칙 shelf_pins {"shelf_pins": ["shelf_1 right: 4 pins for shelf depth 566, rule 2", "shelf_2 left: 4 pins for shelf depth 566, rule 2", "shelf_2 right: 4 pins for shelf depth 566, rule 2", "shelf_3 left: 4 pins for shelf depth 566, rule 2", "shelf_3 right: 4 pins for shelf depth 566, rule 2"]} 
- 문장 기본 10: 정답 채점 통과, 검사기 걸린 규칙 shelf_pins {"shelf_pins": ["shelf_1 right: 4 pins for shelf depth 466, rule 2", "shelf_2 right: 4 pins for shelf depth 466, rule 2", "shelf_3 right: 4 pins for shelf depth 466, rule 2", "shelf_4 left: 4 pins for shelf depth 466, rule 2", "shelf_5 left: 4 pins for shelf depth 466, rule 2"]} 
- 문장 우선순위 01: 정답 채점 통과, 검사기 걸린 규칙 shelf_pins {"shelf_pins": ["shelf_1 right: 4 pins for shelf depth 546, rule 2", "shelf_2 left: 4 pins for shelf depth 546, rule 2", "shelf_2 right: 4 pins for shelf depth 546, rule 2", "shelf_3 left: 4 pins for shelf depth 546, rule 2"]} 
- 문장 우선순위 03: 정답 채점 통과, 검사기 걸린 규칙 shelf_pins {"shelf_pins": ["shelf_1 right: 4 pins for shelf depth 546, rule 2", "shelf_2 left: 4 pins for shelf depth 546, rule 2"]} 
- 문장 우선순위 04: 정답 채점 통과, 검사기 걸린 규칙 shelf_pins {"shelf_pins": ["shelf_1 right: 4 pins for shelf depth 570, rule 2", "shelf_2 left: 4 pins for shelf depth 570, rule 2", "shelf_2 right: 4 pins for shelf depth 570, rule 2", "shelf_3 left: 4 pins for shelf depth 570, rule 2"]} 
- 문장 우선순위 05: 정답 채점 통과, 검사기 걸린 규칙 shelf_pins {"shelf_pins": ["shelf_1 right: 4 pins for shelf depth 546, rule 2", "shelf_2 right: 4 pins for shelf depth 546, rule 2", "shelf_3 right: 4 pins for shelf depth 546, rule 2", "shelf_4 left: 4 pins for shelf depth 546, rule 2", "shelf_5 left: 4 pins for shelf depth 546, rule 2"]} 
- 문장 우선순위 06: 정답 채점 통과, 검사기 걸린 규칙 shelf_pins {"shelf_pins": ["shelf_1 right: 6 pins for shelf depth 616, rule 3", "shelf_2 left: 6 pins for shelf depth 616, rule 3", "shelf_2 right: 6 pins for shelf depth 616, rule 3", "shelf_3 left: 6 pins for shelf depth 616, rule 3"]} 
- 문장 우선순위 07: 정답 채점 통과, 검사기 걸린 규칙 shelf_pins {"shelf_pins": ["shelf_1 right: 4 pins for shelf depth 546, rule 2", "shelf_2 left: 4 pins for shelf depth 546, rule 2", "shelf_2 right: 4 pins for shelf depth 546, rule 2", "shelf_3 left: 4 pins for shelf depth 546, rule 2"]} 
- 문장 우선순위 08: 정답 채점 통과, 검사기 걸린 규칙 shelf_pins {"shelf_pins": ["shelf_1 right: 4 pins for shelf depth 546, rule 2", "shelf_2 left: 4 pins for shelf depth 546, rule 2"]} 
- 문장 우선순위 09: 정답 채점 통과, 검사기 걸린 규칙 shelf_pins {"shelf_pins": ["shelf_1 right: 6 pins for shelf depth 866, rule 3", "shelf_2 left: 6 pins for shelf depth 866, rule 3"]} 
- 문장 우선순위 10: 정답 채점 통과, 검사기 걸린 규칙 shelf_pins {"shelf_pins": ["shelf_1 right: 4 pins for shelf depth 546, rule 2", "shelf_2 left: 4 pins for shelf depth 546, rule 2", "shelf_2 right: 4 pins for shelf depth 546, rule 2", "shelf_3 left: 4 pins for shelf depth 546, rule 2", "shelf_3 right: 4 pins for shelf depth 546, rule 2"]} 
- 문장 우선순위 11: 정답 채점 통과, 검사기 걸린 규칙 shelf_pins {"shelf_pins": ["shelf_1 right: 4 pins for shelf depth 546, rule 2", "shelf_2 right: 4 pins for shelf depth 546, rule 2", "shelf_3 right: 4 pins for shelf depth 546, rule 2", "shelf_4 left: 4 pins for shelf depth 546, rule 2", "shelf_5 left: 4 pins for shelf depth 546, rule 2"]} 
- 문장 우선순위 12: 정답 채점 통과, 검사기 걸린 규칙 shelf_pins {"shelf_pins": ["shelf_1 right: 6 pins for shelf depth 666, rule 3", "shelf_2 left: 6 pins for shelf depth 666, rule 3", "shelf_2 right: 6 pins for shelf depth 666, rule 3", "shelf_3 left: 6 pins for shelf depth 666, rule 3", "shelf_3 right: 6 pins for shelf depth 666, rule 3"]} 

검사기가 보지 않는 것: 고객 요청을 제대로 읽었는지(치수, 문 배치 등)와 한쪽문의 경첩 방향 선호(홀수 문의 마지막 문 오른쪽 등)는 규칙이 아니라 요청과 기본값의 문제라 정답 채점에서만 봅니다.

## 4. 재단표·엣지 샘플

- 기본 하부장 1200x850x580: `results/cutlist/ref_1200x850x580.md` (부재 10개, 경첩(컵 35) 4, 선반 다보 8, 다릿발 6)
- 1500 한쪽문+양문, 상판 덮음: `results/cutlist/ref_1500_onset_1-2.md` (부재 11개, 경첩(컵 35) 6, 선반 다보 8, 다릿발 8)
- 900 싱크대, 뒷판 인셋: `results/cutlist/ref_900_sink_inset.md` (부재 9개, 경첩(컵 35) 4, 선반 다보 8, 다릿발 6)
- AI가 만든 모델 c12 최종: `results/cutlist/ai_c12_final.md`

엣지 판단 근거 (규칙을 받지 않고 기존 규칙에서 추론):

1. 패널 모서리는 다른 판재가 2.5mm 안에 닿아 가리지 않으면 엣지를 붙인다 (선반 옆 1mm 여유는 가려진 것으로 봄)
2. 문은 열리므로 몸통 앞 모서리를 가리지 않는다고 본다: 측판·상하판·칸막이·선반 앞 모서리는 엣지
3. 벽을 향하는 뒤쪽 모서리는 엣지를 붙이지 않는다
4. 뒷판(10mm)은 엣지를 붙이지 않는다
5. 문은 네 모서리 모두 엣지
