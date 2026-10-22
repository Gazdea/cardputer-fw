# cardputer-fw

Прошивки для **M5Stack Cardputer ADV** (ESP32-S3FN8, 8 MB flash, без PSRAM) и канал доставки обновлений.

Форк [bmorcelli/Launcher](https://github.com/bmorcelli/Launcher) (тег **2.9.1**) с собственной разметкой flash,
своей версией и агентом самообновления.

## Что здесь

| Путь | Назначение |
|---|---|
| `manifest.json` | что ставить на устройство: версия, ссылка, sha256, размер (без BOM — его не переваривает ArduinoJson) |
| `catalog.json` | список прошивок, которые можно ставить |
| `tools/build.ps1` | сборка кастомного лаунчера (PlatformIO), версия подставляется в `-DLAUNCHER` |
| `tools/publish.ps1` | релиз в GitHub + перезапись `manifest.json` (sha256/размер/URL) |
| `tools/flash_ota.py` | заливка по сети через WebUI (`/login` → `/OTA` → `/OTAFILE`) |
| `dist/` | собранные образы (в git не попадают) |

## Разметка flash

```
0x0009000  nvs        20 KB
0x000e000  otadata     8 KB
0x0010000  app0        2 MB     <- лаунчер + агент
0x0210000  coredump   64 KB
0x0220000  ...        ~5.5 MB   <- приложения (создаются лаунчером)
```

`app0` увеличен с 1344 KB до 2 MB: стоковый лаунчер занимает 1.36 MB, агенту нужен запас.
`bootToApp` по умолчанию **выключен** — при старте всегда меню, приложение запускается явно.

## Что добавлено к апстриму

| Возможность | Как пользоваться |
|---|---|
| Ручной старт WebUI | меню `WUI` → `my Network`/`AP mode`, либо команда `webui [ap\|sta]` в serial-консоли (115200). Автозапуска при загрузке нет |
| `GET /selfupdate` | проверка: `{local, remote, update, sha256, size}` |
| `POST /selfupdate?install=1` | скачать → сверить sha256 → поставить → перезагрузиться |
| `GET /status` | `{version, heapFree, heapMin, uptimeMs, wifi, ip, sdMounted, manifest, apps[]}` |
| Консоль | `update check`, `update install`, `update url <manifest>` |
| Стеки | SerialConsole 10 KB, httpd 12 KB (TLS+JSON+SD не влезали в 4 KB) |

## Цикл обновления

```
правка кода → tools\build.ps1 -Version 2.9.1-cfwN
            → tools\publish.ps1 -Version ... -File dist\... -Notes "..."
            → на устройстве: update install   (или POST /selfupdate?install=1)
            → устройство: манифест → разница версий → докачка образа в /downloads/_ota/
              → sha256 → установка → перезагрузка
```

Загрузка идёт **чанками по 32 КБ с докачкой**: на слабом Wi-Fi CDN закрывает соединение,
поэтому принятые байты не выбрасываются, а следующий запрос продолжает с того же места.
Полный образ 1.4 MB на этой точке доступа качается минуты — это нормально, обновления редкие.

## Проверено на живой плате

- установка из SD по HTTP (`POST /UPDATE`) — устройство само перезагрузилось в новую прошивку;
- `update check` — TLS до GitHub, разбор манифеста, сравнение версий;
- USB-заливка app-части (`esptool write-flash 0x10000`) с сохранением разметки и SD.

## Безопасность

- WebUI закрыт логином (`wui_usr`/`wui_pwd`), cookie `ESP32SESSION`, Basic-auth нет;
- образ сверяется по `sha256` из манифеста;
- Wi-Fi пароли в `config.conf` на SD зашифрованы (`"secure": true`), но карта всё равно остаётся ключом к сети;
- канал обновления — публичный HTTPS, без подписи: компромисс в пользу простоты. Если понадобится —
  следующий шаг подпись образа (ed25519) и проверка на устройстве.
