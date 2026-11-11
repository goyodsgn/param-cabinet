# step3_priority: 12 / 12 pass all checks

| id | runs | read request | conflict noted | params | absolute_rules | solids | carcass_parts | overall_size | door_count | door_gap | hinge_count | hinge_sides | divider_count | shelf_count | pin_count | leg_count | param count | error |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 | O | O | - | O | O | O | O | O | O | O | O | O | O | O | O | O | 18 |  |
| 02 | O | O | - | O | O | O | O | O | O | O | O | O | O | O | O | O | 29 |  |
| 03 | O | O | - | O | O | O | O | O | O | O | O | O | O | O | O | O | 29 |  |
| 04 | O | O | - | O | O | O | O | O | O | O | O | O | O | O | O | O | 29 |  |
| 05 | O | O | - | O | O | O | O | O | O | O | O | O | O | O | O | O | 30 |  |
| 06 | O | O | - | O | O | O | O | O | O | O | O | O | O | O | O | O | 29 |  |
| 07 | O | O | O | O | O | O | O | O | O | O | O | O | O | O | O | O | 18 |  |
| 08 | O | O | O | O | O | O | O | O | O | O | O | O | O | O | O | O | 18 |  |
| 09 | O | O | O | O | O | O | O | O | O | O | O | O | O | O | O | O | 18 |  |
| 10 | O | O | O | O | O | O | O | O | O | O | O | O | O | O | O | O | 29 |  |
| 11 | O | O | O | O | O | O | O | O | O | O | O | O | O | O | O | O | 29 |  |
| 12 | O | O | - | O | O | O | O | O | O | O | O | O | O | O | O | O | 29 |  |

Pass rate per check (out of the rows where it applies):

- runs: 12 / 12
- read_request: 12 / 12
- conflict_noted: 5 / 5
- params: 12 / 12
- absolute_rules: 12 / 12
- solids: 12 / 12
- carcass_parts: 12 / 12
- overall_size: 12 / 12
- door_count: 12 / 12
- door_gap: 12 / 12
- hinge_count: 12 / 12
- hinge_sides: 12 / 12
- divider_count: 12 / 12
- shelf_count: 12 / 12
- pin_count: 12 / 12
- leg_count: 12 / 12

Notes the model wrote:

- 04: Door thickness set to 18 mm as requested; all other values follow company defaults. / Door count is automatic: ceil(1500/600) = 3 doors, the last (odd) door hinges right.
- 05: Customer asked for exactly 3 shelves: they are spread evenly, so the spaces between shelves are about 156 mm, below the usual 320 mm minimum (explicit customer request overrides the default). / Door count is automatic: ceil(1200/600) = 2 doors, so there is one inner wall at x = 600 and two bays, each with 3 shelves.
- 06: '판 두께 15' was read as t = 15 (sides, top, bottom). Back, dividers, doors and shelves keep their defaults. / W = 1800 needs 3 doors (ceil(1800/600)), so 2 inner walls and 3 bays with shelves are generated automatically.
- 07: Customer asked for 2 doors, but W = 1800 with a maximum door cell width of 600 needs at least ceil(1800/600) = 3 doors (ABSOLUTE rule). / Built with 3 doors (n_doors = automatic), each cell 600 wide, and 2 inner walls behind the door joints.
- 08: The customer asked for doors with no gap. The 2 mm clearance on every side of each door is mandatory (ABSOLUTE), so door_gap stays 2. / Doors are 596 wide and 746 high, with 4 mm between neighbouring doors.
- 09: Customer asked for only 2 shelf pins per side. The pin count rule is ABSOLUTE: pins per side = ceil(span / 500) + 1, so this cabinet gets 3 pins per side of each shelf. / Shelf depth is 866 mm and the pin span is 766 mm, so 2 pins would be 766 mm apart, over the 500 mm limit.
- 10: 요청하신 '다리 4개(네 귀퉁이만)'는 적용하지 않았습니다. 절대 규칙상 다리 중심 간격은 600mm 이하여야 합니다. / 폭 방향 코너 다리 간격이 2300mm이므로 폭 방향 5개 x 깊이 방향 2개 = 총 10개의 다리를 격자로 배치했습니다. / 폭 2400 기준 문은 4개(셀 폭 600), 칸막이 3개가 자동 적용됩니다.
- 11: Customer asked for only 2 hinges per door. The door height is 1596 mm ((1700 - 100) - 2*2), which falls in the 'up to 1600' class. The mandatory rule requires 3 hinges per door, so each door gets 3 hinges.
