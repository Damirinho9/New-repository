# MasterSCADA 3.11 Stage 4 - verified tutorial reference types

Source: official MasterSCADA 3.11 tutorial projects installed under `C:\MasterSCADA Projects\Projects\Tutorials`.

Native tutorial VAVs analyzed:
- `Demo\Demo.vav`
- `Demo_Бак\Demo_Бак.vav`
- `Типизация_демо\Типизация_демо.vav`
- `ПИД-регулятор\ПИД-регулятор.vav`
- `Пример задатчика\Пример задатчика.vav`
- `Demo_Интеллектуальное Здание\Demo_Интеллектуальное здание.vav`

The VAV files are OLE Compound Files. Their native `SysTree`, `ObjTree`, `ItemData`, and `Data` class registry were inspected.

## Computer

Real tutorial nodes consistently use class index 5:
- `Demo.vav -> SysTree/354 -> Компьютер 1`
- `Типизация_демо.vav -> SysTree/19 -> Компьютер 1`
- `ПИД-регулятор.vav -> SysTree/1096 -> Компьютер 1`
- `Demo_Бак.vav -> SysTree/261 -> Управление баком`

Class registry index 5:
- Name: `Компьютер`
- CLSID: `{33A04CE5-4692-11D4-B153-87EB14408E58}`
- ProgID: `Vavobj.Computer.1`
- ItemType: `1` / `titFOLDER`
- ObjectType: `12` / `otComputer`

## Ordinary technological object

Real tutorial nodes consistently use class index 6:
- `Demo_Бак.vav -> Бак`
- `Demo_Интеллектуальное здание.vav -> Напорный бак`
- `ПИД-регулятор.vav -> Объект Управления`
- `Типизация_демо.vav -> ТИ расхода`
- `Demo.vav -> Исполнительные Механизмы`

Class registry index 6:
- Name: `Объект`
- CLSID: `{C974EA66-E284-11D2-95EC-000000000000}`
- ProgID: `Vavobj.VavFolder.1`
- ItemType: `1` / `titFOLDER`
- ObjectType: `9` / `otFolder`

Do not confuse this with the object-tree root CLSID `{B4AFE1A6-850A-4B07-A18B-1FE260E2FAB7}`, ObjectType 8.

## Real analog/value node

`Типизация_демо.vav` contains:
- path: `ObjTree/804971/802384/782844/31/805773`
- Name: `ИзмеренноеЗначение`
- ItemType: `2`
- class index: `29`
- class: `Повторитель`
- CLSID: `{BAF1E982-BDA4-11D5-8568-008048837C1A}`
- ObjectType: `19` / `otRepeater`

This is a real leaf analog node used in an official tutorial.

## Built-in Value class

The `Demo.vav` class registry also contains:
- Name: `Значение`
- CLSID: `{3FFAD3B4-D207-4912-B170-DFEE3C068ADF}`
- ObjectType: `3` / `otValue`

This class is present in the native tutorial class registry, although the selected tutorial trees do not use it as a standalone TreeItem.

## Root controls

- SystemRoot: CLSID `{48EC81C3-3370-11D4-AC35-B6DC66C5D90A}`, ObjectType 7 / `otSystemRoot`
- ObjTree.Root: CLSID `{B4AFE1A6-850A-4B07-A18B-1FE260E2FAB7}`, ObjectType 8 / `otObjectRoot`

## Evidence

Official tutorial files artifact:
- workflow run `44104373639`
- artifact `masterscada-7341268-official-tutorial-projects`

Reference validation:
- workflow run `44106772811`
- artifact `masterscada-7341268-stage4-reference-validation`

Status: `STAGE4_REFERENCE_TYPES=PASS`
