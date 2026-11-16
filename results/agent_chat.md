# agent_chat: conversation test

- Turn 1 pass: 4 / 4
- Final turn pass: 4 / 4
- Final turn, request read correctly: 4 / 4
- Final turn, geometry and company rules: 4 / 4

| id | turn | customer | runs | read | geometry | pass | what went wrong |
|---|---|---|---|---|---|---|---|
| c01 | 1 | 폭 1500, 높이 850, 깊이 600으로 하부장 만들어줘. 세칸짜리인데 가장 왼쪽이 한쪽문이고 양문형이 오른쪽에 오게. | O | O | O | O |  |
| c01 | 2 | 상판이 위를 덮게 바꿔줘. | O | O | O | O |  |
| c08 | 1 | 폭 1500 높이 850 깊이 600. 양문형이 왼쪽에 있고, 오른쪽 끝에 한쪽문 하나. | O | O | O | O |  |
| c08 | 2 | 아 반대로요. 한쪽문이 왼쪽이고 양문이 오른쪽이요. | O | O | O | O |  |
| c13 | 1 | 싱크대 하부장 폭 1200 높이 850 깊이 600, 상판은 없이. 뒷판은 인셋. | O | O | O | O |  |
| c13 | 2 | 선반은 빼고, 문은 세 짝으로 해주세요. | O | O | O | O |  |
| c21 | 1 | 폭 900, 깊이 580, 안쪽 높이가 714 되게 해주세요. | O | O | O | O |  |
| c21 | 2 | 싱크대 넣을 거라 상판은 빼고, 그래도 안쪽 높이는 714 유지해주세요. | O | O | O | O |  |

Pass rate per check, final turn:

- params: 4 / 4
- absolute_rules: 4 / 4
- solids: 4 / 4
- carcass_parts: 4 / 4
- top_panel: 4 / 4
- back_panel: 4 / 4
- overall_size: 4 / 4
- door_count: 4 / 4
- door_gap: 4 / 4
- hinge_count: 4 / 4
- hinge_sides: 4 / 4
- divider_count: 4 / 4
- divider_position: 4 / 4
- shelf_count: 4 / 4
- shelf_spaces: 4 / 4
- pin_count: 4 / 4
- leg_count: 4 / 4

Notes the model wrote (final turn):

- c08: 한쪽문(1칸)은 왼쪽, 양문형(2칸)은 오른쪽으로 배치했습니다 (door_layout=[1,2], 문 3개, 칸당 500mm).
- c21: 싱크대 설치를 위해 상판을 없앴습니다(top 없음). / 상판이 없어 안쪽 높이 714 -> H = 714 + 다리 100 + 하판 18 = 832로 환산했습니다.
