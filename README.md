# cardputer-fw

Прошивки для **M5Stack Cardputer ADV** (ESP32-S3FN8, 8 MB flash, без PSRAM).
Форк [bmorcelli/Launcher](https://github.com/bmorcelli/Launcher) (тег **2.9.1**) со своей версией,
своей разметкой flash и ручным запуском WebUI.

Обновление — **только по USB**. Воздушное обновление пробовали и убрали: на этой точке доступа
образ 1.4 МБ качается ~10 минут, устройство греется и садится. Канал оставлен как история в релизах,
агент из прошивки вырезан.

## Что здесь

| Путь | Назначение |
|---|---|
| `catalog.json` | какие прошивки есть и где лежат |
| `tools/build.ps1` | сборка (PlatformIO), версия подставляется в `-DLAUNCHER` |
| `tools/publish.ps1` | публикация образа в GitHub Releases |
| `tools/usb-flash.ps1` | заливка по USB через esptool: app-часть (по умолчанию) или полный образ |
| `dist/` | собранные образы (в git не попадают) |

## Разметка flash

```
0x0009000  nvs        20 KB
0x000e000  otadata     8 KB
0x0010000  app0        2 MB     <- лаунчер
0x0210000  coredump   64 KB
0x0220000  ...        ~5.5 MB   <- приложения (создаются лаунчером)
```

`app0` увеличен с 1344 KB до 2 MB (сток занимает 1.36 MB). `bootToApp` по умолчанию **выключен**:
при старте всегда меню, приложение запускается явно.

## Что добавлено к апстриму

| Возможность | Как пользоваться |
|---|---|
| Ручной старт WebUI | меню `WUI` → `my Network` / `AP mode`, либо `webui [ap\|sta]` в serial-консоли (115200). Автозапуска нет |
| `GET /status` | `{version, heapFree, heapMin, uptimeMs, wifi, ip, sdMounted, apps[]}` — быстрая проверка состояния, когда WebUI поднят |
| Консоль | `partitions`, `flash firmware <name> <size>`, `wifi ...`, `settings get/set`, `nav`, `webui` |

## Сборка и заливка

```powershell
.\tools\build.ps1 -Version 2.9.1-cfw15
.\tools\usb-flash.ps1 -Port COM6 -File .\dist\Launcher-m5stack-cardputer-2.9.1-cfw15.bin
```

`usb-flash.ps1` по умолчанию пишет только app-часть по `0x10000` — разметка, NVS и SD не трогаются.
`-Full` пишет merged-образ с `0x0` (нужно только при смене разметки; стирает NVS и разделы приложений).

Download mode на Cardputer ADV: тумблер **OFF** → зажать **G0** → включить → отпустить.

## Проверено на живой плате

- USB-заливка app-части с сохранением разметки и SD;
- установка приложения из SD по HTTP (`POST /UPDATE`) с автоматической перезагрузкой;
- запуск/остановка WebUI из консоли, `/status` и `/systeminfo`.

## Безопасность

- WebUI закрыт логином (`wui_usr`/`wui_pwd`), cookie `ESP32SESSION`;
- Wi-Fi пароли в `config.conf` на SD зашифрованы (`"secure": true`);
- канал обновлений отсутствует — прошивку на устройство можно попасть только физически (USB) или
  установив файл с SD, что осознанно выбрано вместо сетевого автообновления.
