# Hexlet acceptance gate - "Установка КОМПАС"

Дисциплина: Инженерная компьютерная графика

Источник: сохраненная страница Hexlet (1.png + 2.png), зафиксированная в аудите материалов.

## Final evidence - exactly 2 screenshots

### 1. KOMPAS-3D
- Full KOMPAS-3D application window is visible.
- A drawing is open.
- The sheet visibly contains the exact text: `Привет, Хекслет!`.

Expected filename:
`01_KOMPAS_3D_Privet_Hexlet.png`

### 2. KOMPAS-Electric
- Full KOMPAS-Electric application window is visible.
- A project and scheme/document sheet are open.
- The sheet visibly contains the exact text: `Привет, Хекслет!`.

Expected filename:
`02_KOMPAS_Electric_Privet_Hexlet.png`

## Reject as final evidence
- EULA/license agreement window;
- installer;
- terminal / PowerShell;
- GitHub Actions / CI logs;
- API/debug logs;
- installation screenshots;
- screenshot without the required text;
- screenshot where the full corresponding application window is not visible.

## Submission format
- One submitted file containing both screenshots (document or archive).
- Native project files are kept only as reserve; the Hexlet page does not list them as mandatory submission files.

## Source restriction
- The Hexlet page states that installation and screenshots are made by the student.
- Installation stages do not need to be photographed.

## Gate
`PASS` only if both expected screenshots exist and satisfy all conditions above.
