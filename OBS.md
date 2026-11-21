OBS: изучение библиотеки и способы интеграции ИИ-ассистента

Задача: разобраться, как из кода управлять OBS и его источниками,
чтобы подключить голосового ИИ-ассистента с аватаром.

Источники: официальная документация OBS (https://obsproject.com/kb/scripting-guide)


1. Через что вообще можно взаимодействовать с OBS

- libobs (C/C++) - ядро программы. Основной путь для нативных плагинов,
  но требует сборки на C++ и привязки к версии OBS, для нас избыточно.
- Скрипты OBS - Python (obspython) и Lua (obslua). Почти все функции
  libobs доступны из скрипта как обычные функции модуля.
- obs-websocket - встроен в OBS 28+, работает по WebSocket+JSON на
  порту 4455. Позволяет управлять OBS из отдельной программы.
- Browser Source - Chromium внутри OBS, умеет показывать HTML/JS/CSS
  с прозрачным фоном. Удобно для аватара и эмоций.

Для проекта нужен Python, поэтому основной вариант - Python-скрипт
внутри OBS или внешний Python-сервис, который связан с OBS через
obs-websocket.


2. Жизненный цикл Python-скрипта в OBS

OBS сам вызывает набор глобальных функций:

  script_description()      - описание в окне Scripts
  script_defaults(settings) - значения настроек по умолчанию
  script_load(settings)     - инициализация: подписки, хоткеи
  script_update(settings)   - вызывается при смене настроек
  script_properties()       - построение панели настроек
  script_tick(seconds)      - каждый кадр
  script_save(settings)     - перед сохранением настроек
  script_unload()           - при выгрузке скрипта

Что важно учитывать:
- при старте OBS скрипты грузятся раньше сцен и источников, поэтому
  искать свои источники сразу в script_load() не стоит, лучше ждать
  события OBS_FRONTEND_EVENT_FINISHED_LOADING;
- script_tick в Python вызывается каждый кадр и из-за GIL может сильно
  нагружать процесс, для периодических задач лучше timer_add;
- в script_unload нужно снимать таймеры, хоткеи и колбэки, иначе
  после выгрузки скрипта они остаются висеть.

Таймеры и хоткеи из скрипта:

  timer_add(callback, milliseconds)
  timer_remove(callback)

  obs_hotkey_register_frontend(name, description, callback)
  obs_hotkey_unregister(callback)

Настройки и панель скрипта строятся через obs_properties_add_text /
add_bool / add_int / add_list / add_path, значения хранятся в obs_data_t.

Отдельно про Python: интерпретатор в OBS не встроен, нужен установленный
Python (обычно 64-битный) и указание пути в Tools -> Scripts -> Python
Settings. Зависимости ставятся в тот же Python через pip.


3. Сцены и источники из скрипта

Поиск и создание:

  obs_get_source_by_name(name)
  obs_source_create(id, name, settings, None)
  obs_source_release(source)

Настройки источника меняются так:

  settings = obs_source_get_settings(source)
  obs_data_set_string(settings, "file", path)
  obs_source_update(source, settings)
  obs_data_release(settings)

Сцены и элементы сцены:

  obs_frontend_get_current_scene()      - текущая сцена, нужен release
  obs_frontend_set_current_scene(scene) - переключить сцену
  obs_scene_from_source(source)         - получить obs_scene_t
  obs_scene_add(scene, source)          - добавить источник в сцену
  obs_scene_find_source(scene, name)
  obs_scene_enum_items(scene)           - список элементов сцены
  sceneitem_list_release(items)

  obs_sceneitem_set_visible(item, bool)
  obs_sceneitem_set_pos(item, vec2)
  obs_sceneitem_set_scale(item, vec2)
  obs_sceneitem_set_rot(item, degrees)
  obs_sceneitem_set_crop(item, crop)

Аудио и медиа:

  obs_source_set_volume(source, 1.0)    - 1.0 это 0 dB
  obs_source_set_muted(source, True)
  obs_source_media_restart(source)      - перезапустить видео/аудио
  obs_source_media_play_pause(source, pause)
  obs_source_media_get_state(source)

Ссылки: obs_get_source_by_name, obs_source_create, obs_frontend_get_current_scene
возвращают новую ссылку, её надо освобождать через obs_source_release.
obs_scene_from_source возвращает заимствованную ссылку, её освобождать
нельзя. Если этого не соблюдать, OBS может упасть при выходе.


4. Какие источники подходят для аватара и голоса

image_source - статичная картинка.
  Настройки: "file" (путь), "unload", "linear_alpha".
  Меняется через obs_source_update с новым путём.
  Подходит для набора готовых эмоций (happy.png, sad.png и т.д.).

slideshow - слайд-шоу картинок.
  Настройки: "files" (массив объектов с путями), "slide_time", "transition"
  ("fade", "cut", "swipe", "slide"), "loop", "randomize".
  Переход между слайдами можно делать через obs_source_media_next.

browser_source - HTML-страница внутри OBS.
  Настройки: "url", "width", "height", "css", "shutdown",
  "restart_when_active", "reroute_audio" (звук страницы идёт в OBS).
  Для аватара это удобнее всего: прозрачный фон, анимации, эмоции,
  звук TTS. Страница может держать WebSocket с нашей программой и
  получать команды вида {"type": "emotion", "value": "happy"} без
  перезагрузки. Смена url перезагружает страницу, поэтому для частых
  состояний её лучше не менять.
  Также у страницы есть window.obsstudio: getCurrentScene, setCurrentScene,
  startRecording, stopRecording и т.д., но доступ к ним включается
  в настройках источника.

text_gdiplus - текст на экране.
  Настройки: "text", "font" (face, size, flags), "color", "outline",
  "extents_wrap", "extents_cx". Годится для субтитров и статуса
  ассистента ("слушаю", "думаю", "говорю").

ffmpeg_source - видео или аудио файл.
  Настройки: "is_local_file", "local_file", "looping",
  "restart_on_activate", "clear_on_media_end".
  Можно использовать для TTS: сохранили wav, обновили local_file,
  вызвали obs_source_media_restart, аватар в это время анимирует рот.


5. obs-websocket как вариант управления из внешнего Python

Так OBS можно управлять из отдельного процесса, не загружая скрипты.
Включается в Tools -> WebSocket Server Settings, порт 4455, можно
задать пароль. Обмен идёт через JSON-сообщения с полем op: запросы,
ответы, события, пакеты запросов.

Удобные Python-клиенты: obsws-python (обычный) и simpleobsws (async).

Пример на obsws-python:

  from obsws_python import ReqClient

  cl = ReqClient(host="127.0.0.1", port=4455, password="pass", timeout=3)
  cl.set_current_program_scene("AI Assistant")
  cl.set_input_settings("AI Avatar", {"url": "http://127.0.0.1:8765/"}, overlay=True)
  cl.trigger_media_input_action("AI Voice", "OBS_WEBSOCKET_MEDIA_INPUT_ACTION_RESTART")

Из запросов для нас полезны:
- сцены: GetSceneList, GetCurrentProgramScene, SetCurrentProgramScene;
- источники: GetInputList, CreateInput, SetInputSettings, RemoveInput,
  SetInputVolume, SetInputMute, PressInputPropertiesButton;
- элементы сцены: GetSceneItemList, SetSceneItemEnabled,
  SetSceneItemTransform;
- медиа: GetMediaInputStatus, TriggerMediaInputAction;
- служебное: GetSourceScreenshot, SaveSourceScreenshot, BroadcastCustomEvent.

События, на которые можно реагировать: CurrentProgramSceneChanged,
InputMuteStateChanged, MediaInputPlaybackEnded, StreamStateChanged,
CustomEvent. Из них можно делать реакцию ассистента: закончил говорить,
сменилась сцена, началась запись.


6. Пример скрипта для OBS

Ниже небольшой рабочий каркас: скрипт при загрузке создаёт источник
аватара (браузер) и источник для картинки эмоции в текущей сцене.
Это не весь ассистент, но показывает основные вызовы API.

    import obspython as obs

    AVATAR = "AI Avatar"
    EMOTION = "AI Emotion"

    def log(msg):
        print("[AI] " + str(msg))

    def current_scene():
        scene_source = obs.obs_frontend_get_current_scene()
        if not scene_source:
            return None, None
        scene = obs.obs_scene_from_source(scene_source)
        return scene_source, scene

    def create_browser_source():
        settings = obs.obs_data_create()
        obs.obs_data_set_string(settings, "url", "http://127.0.0.1:8765/")
        obs.obs_data_set_int(settings, "width", 1920)
        obs.obs_data_set_int(settings, "height", 1080)
        obs.obs_data_set_bool(settings, "reroute_audio", True)
        obs.obs_data_set_bool(settings, "shutdown", False)
        src = obs.obs_source_create("browser_source", AVATAR, settings, None)
        obs.obs_data_release(settings)
        return src

    def add_to_scene(source):
        scene_source, scene = current_scene()
        if scene and source:
            obs.obs_scene_add(scene, source)
        if scene_source:
            obs.obs_source_release(scene_source)

    def set_emotion(path):
        src = obs.obs_get_source_by_name(EMOTION)
        if src:
            settings = obs.obs_source_get_settings(src)
            obs.obs_data_set_string(settings, "file", path)
            obs.obs_source_update(src, settings)
            obs.obs_data_release(settings)
        else:
            settings = obs.obs_data_create()
            obs.obs_data_set_string(settings, "file", path)
            src = obs.obs_source_create("image_source", EMOTION, settings, None)
            obs.obs_data_release(settings)
            add_to_scene(src)
        if src:
            obs.obs_source_release(src)

    def on_loaded(event):
        # ждём, пока OBS догрузит сцены и источники
        if event == obs.OBS_FRONTEND_EVENT_FINISHED_LOADING:
            src = obs.obs_get_source_by_name(AVATAR)
            if src:
                obs.obs_source_release(src)
                return
            src = create_browser_source()
            add_to_scene(src)
            if src:
                obs.obs_source_release(src)
                log("avatar ready")

    def script_load(settings):
        obs.obs_frontend_add_event_callback(on_loaded, None)

    def script_unload():
        obs.obs_frontend_remove_event_callback(on_loaded, None)

    def script_description():
        return "AI assistant: avatar and emotion sources"

Для сервиса внутри скрипта: timer_add удобно использовать как цикл
опросов (например, проверять очередь сообщений от ИИ раз в 100 мс).


7. Выводы

- Для управления источниками из скрипта хватает obs_source_*,
  obs_scene_* и obs_sceneitem_*.
- Лучший вариант аватара - browser_source с прозрачным фоном: эмоции
  и анимацию проще делать на HTML/JS, а не через static-картинки.
- Для голоса подходит ffmpeg_source с TTS-файлом, либо звук напрямую
  из страницы браузера при включённом reroute_audio.
- Если ИИ-сервис вынести отдельно, связь с OBS проще делать через
  obs-websocket, а скрипт в OBS оставить для настроек и хоткеев.
- Главные грабли: утечки ссылок, работа из чужих потоков и обращение
  к источникам до того, как OBS их загрузил.