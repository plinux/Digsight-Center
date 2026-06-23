import {sortedConsistMembers} from "./consist-helpers.js";

export const DEFAULT_FUNCTION_ICON_CATALOG = {
  "version": 1,
  "description": "车辆功能键本地图标目录。外部系统图标名到本地图标 key 的转换关系保存在 config/function-icon-mappings/。",
  "default_icon": "function-generic",
  "icons": {
    "function-generic": {
      "path": "assets/icons/functions/function-generic.svg",
      "label": "功能",
      "source": "local-generated",
      "license": "project-local",
      "keywords": [
        "功能",
        "未分类"
      ]
    },
    "emergency-brake": {
      "path": "assets/icons/functions/emergency-brake.svg",
      "label": "紧急刹车",
      "source": "local-generated",
      "license": "project-local",
      "keywords": [
        "紧急刹车",
        "紧急停车",
        "急停",
        "brake",
        "handbrake"
      ]
    },
    "window-toggle": {
      "path": "assets/icons/functions/window-toggle.svg",
      "label": "车窗开关",
      "source": "local-generated",
      "license": "project-local",
      "keywords": [
        "车窗",
        "开窗",
        "关窗",
        "window",
        "车窗开关"
      ]
    },
    "cab-light": {
      "path": "assets/icons/functions/cab-light.svg",
      "label": "驾驶室灯",
      "source": "local-generated",
      "license": "project-local",
      "keywords": [
        "驾驶室灯",
        "cab light",
        "cockpit_light_left",
        "cockpit_light_right"
      ]
    },
    "compressor": {
      "path": "assets/icons/functions/compressor.svg",
      "label": "空压机",
      "source": "local-generated",
      "license": "project-local",
      "keywords": [
        "空压机",
        "compressor"
      ]
    },
    "coupler": {
      "path": "assets/icons/functions/coupler.svg",
      "label": "连挂",
      "source": "local-generated",
      "license": "project-local",
      "keywords": [
        "连挂",
        "解挂",
        "couple",
        "coupler"
      ]
    },
    "brake-release": {
      "path": "assets/icons/functions/brake-release.svg",
      "label": "缓解",
      "source": "local-generated",
      "license": "project-local",
      "keywords": [
        "缓解",
        "解除制动",
        "brake release",
        "sound_brake"
      ]
    },
    "pantograph": {
      "path": "assets/icons/functions/pantograph.svg",
      "label": "升降弓",
      "source": "local-generated",
      "license": "project-local",
      "keywords": [
        "升降弓",
        "升弓",
        "降弓",
        "pantograph",
        "take_power"
      ]
    },
    "sound-generic": {
      "path": "assets/icons/functions/sound-generic.svg",
      "label": "声音",
      "source": "local-generated",
      "license": "project-local",
      "keywords": [
        "声音",
        "音效",
        "sound",
        "轮轨声"
      ]
    },
    "horn": {
      "path": "assets/icons/functions/horn.svg",
      "label": "鸣笛",
      "source": "local-generated",
      "license": "project-local",
      "keywords": [
        "鸣笛",
        "汽笛",
        "电笛",
        "风笛",
        "horn",
        "bugle",
        "whistle"
      ]
    },
    "light-front": {
      "path": "assets/icons/functions/light-front.svg",
      "label": "前灯",
      "source": "local-generated",
      "license": "project-local",
      "keywords": [
        "灯",
        "大灯",
        "头灯",
        "行车灯",
        "main_beam",
        "light"
      ]
    },
    "light-rear": {
      "path": "assets/icons/functions/light-rear.svg",
      "label": "尾灯",
      "source": "local-generated",
      "license": "project-local",
      "keywords": [
        "尾灯",
        "红灯",
        "back_light"
      ]
    },
    "door": {
      "path": "assets/icons/functions/door.svg",
      "label": "车门开关",
      "source": "local-generated",
      "license": "project-local",
      "keywords": [
        "车门",
        "开门",
        "关门",
        "door",
        "车门开关"
      ]
    },
    "sander": {
      "path": "assets/icons/functions/sander.svg",
      "label": "撒沙",
      "source": "local-generated",
      "license": "project-local",
      "keywords": [
        "撒沙",
        "sanden"
      ]
    },
    "engine": {
      "path": "assets/icons/functions/engine.svg",
      "label": "发动机",
      "source": "local-generated",
      "license": "project-local",
      "keywords": [
        "发动机",
        "柴油机",
        "机车启动",
        "engine",
        "main"
      ]
    },
    "curve-sound": {
      "path": "assets/icons/functions/curve-sound.svg",
      "label": "曲线声",
      "source": "local-generated",
      "license": "project-local",
      "keywords": [
        "曲线声",
        "道岔摩擦声",
        "curve_sound"
      ]
    },
    "shunting-mode": {
      "path": "assets/icons/functions/shunting-mode.svg",
      "label": "调车模式",
      "source": "local-generated",
      "license": "project-local",
      "keywords": [
        "调车模式",
        "hump_funk",
        "hump_gear",
        "neutral"
      ]
    },
    "music": {
      "path": "assets/icons/functions/music.svg",
      "label": "音乐",
      "source": "local-generated",
      "license": "project-local",
      "keywords": [
        "音乐",
        "发车音乐",
        "clef"
      ]
    },
    "mute": {
      "path": "assets/icons/functions/mute.svg",
      "label": "静音",
      "source": "local-generated",
      "license": "project-local",
      "keywords": [
        "静音",
        "mute",
        "quiter"
      ]
    },
    "fan": {
      "path": "assets/icons/functions/fan.svg",
      "label": "风扇",
      "source": "local-generated",
      "license": "project-local",
      "keywords": [
        "风扇",
        "散热风扇",
        "fan"
      ]
    },
    "bell": {
      "path": "assets/icons/functions/bell.svg",
      "label": "铃声",
      "source": "local-generated",
      "license": "project-local",
      "keywords": [
        "铃声",
        "铃铛",
        "发车铃",
        "bell"
      ]
    },
    "announcement": {
      "path": "assets/icons/functions/announcement.svg",
      "label": "广播",
      "source": "local-generated",
      "license": "project-local",
      "keywords": [
        "广播",
        "车站广播",
        "发车广播",
        "announcement"
      ]
    },
    "signal": {
      "path": "assets/icons/functions/signal.svg",
      "label": "信号灯",
      "source": "local-generated",
      "license": "project-local",
      "keywords": [
        "信号",
        "红灯",
        "黄灯",
        "绿灯",
        "停车",
        "减速",
        "限速",
        "signal"
      ]
    },
    "radio": {
      "path": "assets/icons/functions/radio.svg",
      "label": "手台",
      "source": "local-generated",
      "license": "project-local",
      "keywords": [
        "手台",
        "对讲机",
        "radio"
      ]
    },
    "volume-up": {
      "path": "assets/icons/functions/volume-up.svg",
      "label": "音量加",
      "source": "local-generated",
      "license": "project-local",
      "keywords": [
        "音量加",
        "提高音量",
        "声音加",
        "lou­der",
        "louder"
      ]
    },
    "volume-down": {
      "path": "assets/icons/functions/volume-down.svg",
      "label": "音量减",
      "source": "local-generated",
      "license": "project-local",
      "keywords": [
        "音量减",
        "降低音量",
        "声音减"
      ]
    },
    "steam": {
      "path": "assets/icons/functions/steam.svg",
      "label": "蒸汽/发烟",
      "source": "local-generated",
      "license": "project-local",
      "keywords": [
        "蒸汽",
        "发烟",
        "steam"
      ]
    },
    "warning": {
      "path": "assets/icons/functions/warning.svg",
      "label": "告警",
      "source": "local-generated",
      "license": "project-local",
      "keywords": [
        "告警",
        "警告",
        "异常",
        "LKJ",
        "sifa",
        "warning"
      ]
    },
    "drain-valve": {
      "path": "assets/icons/functions/drain-valve.svg",
      "label": "泄压/排水",
      "source": "local-generated",
      "license": "project-local",
      "keywords": [
        "泄压",
        "排水",
        "drain_valve"
      ]
    },
    "injector": {
      "path": "assets/icons/functions/injector.svg",
      "label": "注水器",
      "source": "local-generated",
      "license": "project-local",
      "keywords": [
        "注水",
        "注油",
        "injector"
      ]
    },
    "beacon-light": {
      "path": "assets/icons/functions/beacon-light.svg",
      "label": "旋转警示灯",
      "source": "local-generated",
      "license": "project-local",
      "keywords": [
        "旋转警示灯",
        "车顶灯",
        "标志灯",
        "all_round_light",
        "rundumleuchte"
      ]
    },
    "number-board-light": {
      "path": "assets/icons/functions/number-board-light.svg",
      "label": "车号灯",
      "source": "local-generated",
      "license": "project-local",
      "keywords": [
        "车号灯",
        "灯牌",
        "数字灯",
        "licence_plate_light",
        "nummernschild_light"
      ]
    },
    "dashboard-light": {
      "path": "assets/icons/functions/dashboard-light.svg",
      "label": "仪表灯",
      "source": "local-generated",
      "license": "project-local",
      "keywords": [
        "仪表灯",
        "仪表台灯",
        "控制台灯",
        "tish_lamp",
        "tischlampe"
      ]
    },
    "rail-crossing": {
      "path": "assets/icons/functions/rail-crossing.svg",
      "label": "道口信号",
      "source": "local-generated",
      "license": "project-local",
      "keywords": [
        "道口信号",
        "叉道鸣笛",
        "rail_crossing"
      ]
    },
    "coal-shovel": {
      "path": "assets/icons/functions/coal-shovel.svg",
      "label": "加煤",
      "source": "local-generated",
      "license": "project-local",
      "keywords": [
        "加煤",
        "铲煤",
        "加煤机",
        "scoop_coal",
        "kohle_schaufeln"
      ]
    },
    "brake-delay": {
      "path": "assets/icons/functions/brake-delay.svg",
      "label": "惯性停车",
      "source": "local-generated",
      "license": "project-local",
      "keywords": [
        "惯性停车",
        "延迟制动",
        "brake_delay"
      ]
    },
    "coach-light": {
      "path": "assets/icons/functions/coach-light.svg",
      "label": "车厢灯",
      "source": "local-generated",
      "license": "project-local",
      "keywords": [
        "车厢灯",
        "室内灯",
        "coach_light",
        "interior_light"
      ]
    },
    "step-light": {
      "path": "assets/icons/functions/step-light.svg",
      "label": "踏脚灯",
      "source": "local-generated",
      "license": "project-local",
      "keywords": [
        "踏脚灯",
        "脚踏灯",
        "step_light"
      ]
    },
    "destination-sign": {
      "path": "assets/icons/functions/destination-sign.svg",
      "label": "方向牌灯",
      "source": "local-generated",
      "license": "project-local",
      "keywords": [
        "方向牌灯",
        "destination_plate_light",
        "路牌灯"
      ]
    },
    "parking-brake": {
      "path": "assets/icons/functions/parking-brake.svg",
      "label": "手制动",
      "source": "local-generated",
      "license": "project-local",
      "keywords": [
        "手制动",
        "手刹",
        "parking_brake"
      ]
    },
    "water-pump": {
      "path": "assets/icons/functions/water-pump.svg",
      "label": "抽水泵",
      "source": "local-generated",
      "license": "project-local",
      "keywords": [
        "抽水泵",
        "给水泵",
        "water_pump"
      ]
    },
    "firebox": {
      "path": "assets/icons/functions/firebox.svg",
      "label": "火箱",
      "source": "local-generated",
      "license": "project-local",
      "keywords": [
        "火箱",
        "firebox"
      ]
    },
    "generator": {
      "path": "assets/icons/functions/generator.svg",
      "label": "发电机",
      "source": "local-generated",
      "license": "project-local",
      "keywords": [
        "发电机",
        "generator"
      ]
    },
    "preheater": {
      "path": "assets/icons/functions/preheater.svg",
      "label": "内燃机预热",
      "source": "local-generated",
      "license": "project-local",
      "keywords": [
        "内燃机预热",
        "预热",
        "preheat"
      ]
    },
    "hood": {
      "path": "assets/icons/functions/hood.svg",
      "label": "引擎盖",
      "source": "local-generated",
      "license": "project-local",
      "keywords": [
        "引擎盖",
        "打开引擎盖",
        "关闭引擎盖",
        "hood_open",
        "hood_close"
      ]
    },
    "turntable": {
      "path": "assets/icons/functions/turntable.svg",
      "label": "转车台",
      "source": "local-generated",
      "license": "project-local",
      "keywords": [
        "转车台",
        "向左旋转",
        "向右旋转",
        "turntable"
      ]
    },
    "load-mode": {
      "path": "assets/icons/functions/load-mode.svg",
      "label": "重载",
      "source": "local-generated",
      "license": "project-local",
      "keywords": [
        "重载",
        "重车模式",
        "weight"
      ]
    },
    "load-lift": {
      "path": "assets/icons/functions/load-lift.svg",
      "label": "升降货",
      "source": "local-generated",
      "license": "project-local",
      "keywords": [
        "升降货",
        "超重货上升",
        "超重货下降",
        "load_lift"
      ]
    },
    "rpm-up": {
      "path": "assets/icons/functions/rpm-up.svg",
      "label": "内燃机提速",
      "source": "local-generated",
      "license": "project-local",
      "keywords": [
        "内燃机提速",
        "rpm_up",
        "diesel_regulation_step_up"
      ]
    },
    "rpm-down": {
      "path": "assets/icons/functions/rpm-down.svg",
      "label": "内燃机减速",
      "source": "local-generated",
      "license": "project-local",
      "keywords": [
        "内燃机减速",
        "rpm_down",
        "diesel_regulation_step_down"
      ]
    },
    "rail-sound": {
      "path": "assets/icons/functions/rail-sound.svg",
      "label": "轮轨声",
      "source": "local-generated",
      "license": "project-local",
      "keywords": [
        "轮轨声",
        "rail_kick"
      ]
    },
    "crane": {
      "path": "assets/icons/functions/crane.svg",
      "label": "吊车",
      "source": "local-generated",
      "license": "project-local",
      "keywords": [
        "吊车",
        "crane",
        "Kran"
      ]
    },
    "crane-rotate-left": {
      "path": "assets/icons/functions/crane-rotate-left.svg",
      "label": "吊车左转",
      "source": "local-generated",
      "license": "project-local",
      "keywords": [
        "吊车左转",
        "吊臂左转",
        "crane_rotate_left"
      ]
    },
    "crane-rotate-right": {
      "path": "assets/icons/functions/crane-rotate-right.svg",
      "label": "吊车右转",
      "source": "local-generated",
      "license": "project-local",
      "keywords": [
        "吊车右转",
        "吊臂右转",
        "crane_rotate_right"
      ]
    },
    "crane-boom-up": {
      "path": "assets/icons/functions/crane-boom-up.svg",
      "label": "吊臂升",
      "source": "local-generated",
      "license": "project-local",
      "keywords": [
        "吊臂升",
        "吊臂上升",
        "crane_boom_up"
      ]
    },
    "crane-boom-down": {
      "path": "assets/icons/functions/crane-boom-down.svg",
      "label": "吊臂降",
      "source": "local-generated",
      "license": "project-local",
      "keywords": [
        "吊臂降",
        "吊臂下降",
        "crane_boom_down"
      ]
    },
    "crane-boom-extend": {
      "path": "assets/icons/functions/crane-boom-extend.svg",
      "label": "吊臂伸出",
      "source": "local-generated",
      "license": "project-local",
      "keywords": [
        "吊臂伸出",
        "伸臂",
        "crane_boom_extend"
      ]
    },
    "crane-boom-retract": {
      "path": "assets/icons/functions/crane-boom-retract.svg",
      "label": "吊臂缩回",
      "source": "local-generated",
      "license": "project-local",
      "keywords": [
        "吊臂缩回",
        "缩臂",
        "crane_boom_retract"
      ]
    },
    "crane-hook-up": {
      "path": "assets/icons/functions/crane-hook-up.svg",
      "label": "吊钩升",
      "source": "local-generated",
      "license": "project-local",
      "keywords": [
        "吊钩升",
        "吊钩上升",
        "crane_hook_up"
      ]
    },
    "crane-hook-down": {
      "path": "assets/icons/functions/crane-hook-down.svg",
      "label": "吊钩降",
      "source": "local-generated",
      "license": "project-local",
      "keywords": [
        "吊钩降",
        "吊钩下降",
        "crane_hook_down"
      ]
    },
    "crane-outrigger": {
      "path": "assets/icons/functions/crane-outrigger.svg",
      "label": "支腿",
      "source": "local-generated",
      "license": "project-local",
      "keywords": [
        "支腿",
        "支撑",
        "crane_outrigger"
      ]
    },
    "crane-free-run": {
      "path": "assets/icons/functions/crane-free-run.svg",
      "label": "自由拖行",
      "source": "local-generated",
      "license": "project-local",
      "keywords": [
        "自由拖行",
        "Freilauf",
        "crane_free_run"
      ]
    },
    "whistle-short": {
      "path": "assets/icons/functions/whistle-short.svg",
      "label": "短鸣汽笛",
      "source": "local-generated",
      "license": "project-local",
      "keywords": [
        "短鸣汽笛",
        "短鸣笛",
        "短汽笛",
        "whistle_short",
        "short whistle"
      ]
    },
    "whistle-long": {
      "path": "assets/icons/functions/whistle-long.svg",
      "label": "长鸣汽笛",
      "source": "local-generated",
      "license": "project-local",
      "keywords": [
        "长鸣汽笛",
        "长鸣笛",
        "长汽笛",
        "whistle_long",
        "long whistle"
      ]
    },
    "horn-low": {
      "path": "assets/icons/functions/horn-low.svg",
      "label": "低音风笛",
      "source": "local-generated",
      "license": "project-local",
      "keywords": [
        "低音风笛",
        "低音汽笛",
        "低音鸣笛",
        "horn_low",
        "low horn"
      ]
    },
    "horn-high": {
      "path": "assets/icons/functions/horn-high.svg",
      "label": "高音风笛",
      "source": "local-generated",
      "license": "project-local",
      "keywords": [
        "高音风笛",
        "高音汽笛",
        "高音鸣笛",
        "horn_high",
        "high horn"
      ]
    },
    "horn-mixed": {
      "path": "assets/icons/functions/horn-mixed.svg",
      "label": "混合鸣笛",
      "source": "local-generated",
      "license": "project-local",
      "keywords": [
        "混合鸣笛",
        "混音鸣笛",
        "双鸣笛",
        "horn_two_sound",
        "mixed horn"
      ]
    },
    "electric-whistle": {
      "path": "assets/icons/functions/electric-whistle.svg",
      "label": "电笛",
      "source": "local-generated",
      "license": "project-local",
      "keywords": [
        "电笛",
        "短电笛",
        "长电笛",
        "electric whistle"
      ]
    }
  },
  "mappings": {
    "empty": "function-generic",
    "车窗开关": "window-toggle",
    "开窗": "window-toggle",
    "关窗": "window-toggle",
    "紧急刹车": "emergency-brake",
    "紧急停车": "emergency-brake",
    "急停": "emergency-brake",
    "手刹": "parking-brake",
    "handbrake": "emergency-brake",
    "驾驶室灯": "cab-light",
    "cockpit_light_left": "cab-light",
    "cockpit_light_right": "cab-light",
    "空压机": "compressor",
    "compressor": "compressor",
    "连挂": "coupler",
    "解挂": "coupler",
    "couple": "coupler",
    "coupler": "coupler",
    "缓解": "brake-release",
    "解除制动": "brake-release",
    "sound_brake": "brake-release",
    "升降弓": "pantograph",
    "升弓": "pantograph",
    "降弓": "pantograph",
    "forward_take_power": "pantograph",
    "backward_take_power": "pantograph",
    "sound1": "sound-generic",
    "sound2": "sound-generic",
    "轮轨声": "rail-sound",
    "音效": "sound-generic",
    "horn_high": "horn-high",
    "horn_low": "horn-low",
    "bugle": "horn-mixed",
    "whistle_short": "whistle-short",
    "whistle_long": "whistle-long",
    "鸣笛": "horn",
    "短鸣笛": "whistle-short",
    "长鸣笛": "whistle-long",
    "短汽笛": "whistle-short",
    "长汽笛": "whistle-long",
    "短风笛": "horn",
    "长风笛": "horn",
    "短电笛": "electric-whistle",
    "长电笛": "electric-whistle",
    "电笛": "electric-whistle",
    "main_beam": "light-front",
    "main_beam2": "light-front",
    "light": "light-front",
    "light2": "light-front",
    "大灯": "light-front",
    "头灯": "light-front",
    "行车灯": "light-front",
    "前向大灯": "light-front",
    "后向大灯": "light-front",
    "白灯无码": "light-front",
    "back_light": "light-rear",
    "前红灯": "light-rear",
    "后红灯": "light-rear",
    "尾灯": "light-rear",
    "door_close": "door",
    "车门": "door",
    "开门": "door",
    "关门": "door",
    "sanden": "sander",
    "撒沙": "sander",
    "main": "engine",
    "发动机": "engine",
    "柴油机": "engine",
    "机车启动": "engine",
    "curve_sound": "curve-sound",
    "道岔摩擦声": "curve-sound",
    "hump_funk": "shunting-mode",
    "hump_gear": "shunting-mode",
    "neutral": "shunting-mode",
    "调车模式": "shunting-mode",
    "clef": "music",
    "发车音乐": "music",
    "mute": "mute",
    "quiter": "mute",
    "静音模式": "mute",
    "fan": "fan",
    "风扇": "fan",
    "散热风扇": "fan",
    "bell": "bell",
    "铃声": "bell",
    "铃铛": "bell",
    "发车铃": "bell",
    "车站广播": "announcement",
    "发车广播": "announcement",
    "站台广播": "announcement",
    "interior_light": "coach-light",
    "机舱灯": "cab-light",
    "rail_kick": "rail-sound",
    "horn_two_sound": "horn-mixed",
    "sound3": "sound-generic",
    "sound4": "sound-generic",
    "sound5": "sound-generic",
    "dump_steam": "engine",
    "diesel_generator": "generator",
    "generator": "generator",
    "头尾灯": "light-front",
    "cycle_light": "light-front",
    "coach_side_light_off": "coach-light",
    "coach_side_light_off_2": "coach-light",
    "检修灯": "cab-light",
    "cabin_light": "cab-light",
    "司机室灯": "cab-light",
    "door_open": "door",
    "车门开关": "door",
    "关门声": "door",
    "开关门": "door",
    "关窗声": "window-toggle",
    "decouple": "coupler",
    "挂钩": "coupler",
    "连挂解挂": "coupler",
    "连解挂": "coupler",
    "weight": "load-mode",
    "重车模式": "load-mode",
    "开关": "function-generic",
    "红黄灯停车": "signal",
    "黄灯减速": "signal",
    "绿灯通过": "signal",
    "红黄灯": "signal",
    "注意限速": "signal",
    "红灯停车": "signal",
    "信号异常": "signal",
    "调车信号": "signal",
    "黄二灯": "signal",
    "绿黄灯": "signal",
    "双黄灯": "signal",
    "黄二灯注意": "signal",
    "注意停车": "signal",
    "手台": "radio",
    "手台1": "radio",
    "手台2": "radio",
    "司机手台": "radio",
    "LKJ": "warning",
    "sifa": "warning",
    "warning": "warning",
    "车距警告": "warning",
    "监控运行": "warning",
    "泄压": "drain-valve",
    "drain_valve": "drain-valve",
    "steam": "steam",
    "发烟器": "steam",
    "injector": "injector",
    "lou­der": "volume-up",
    "louder": "volume-up",
    "降低音量": "volume-down",
    "air_pump": "compressor",
    "压缩机": "compressor",
    "近光灯": "light-front",
    "远光灯": "light-front",
    "前头灯": "light-front",
    "后远光灯": "light-front",
    "前远光灯": "light-front",
    "sidelights": "light-front",
    "1端红灯": "light-rear",
    "2端红灯": "light-rear",
    "高音汽笛": "horn-high",
    "低音汽笛": "horn-low",
    "汽笛": "horn",
    "高音风笛": "horn-high",
    "低音风笛": "horn-low",
    "长低音风笛": "horn-low",
    "短低音风笛": "horn-low",
    "长高音风笛": "horn-high",
    "鸣笛1": "horn",
    "鸣笛2": "horn",
    "双鸣笛": "horn-mixed",
    "弯道摩擦声": "curve-sound",
    "轨道摩擦声": "curve-sound",
    "曲线摩擦声": "curve-sound",
    "音效开关": "sound-generic",
    "列车缓解": "brake-release",
    "刹车制动": "emergency-brake",
    "紧急制动": "emergency-brake",
    "diesel_regulation_step_down": "rpm-down",
    "diesel_regulation_step_up": "rpm-up",
    "车站广播1": "announcement",
    "车站广播2": "announcement",
    "destination_plate_light": "destination-sign",
    "静音": "mute",
    "音乐": "music",
    "音乐1": "music",
    "音乐2": "music",
    "fan_strong": "fan",
    "风机": "fan",
    "道岔限速": "signal",
    "驾驶室门": "door",
    "室内灯": "coach-light",
    "机械室灯": "cab-light",
    "1端驾驶室灯": "cab-light",
    "2端驾驶室灯": "cab-light",
    "LKJ行车监控": "warning",
    "行车监控": "warning",
    "牵引模式": "engine",
    "推进模式": "engine",
    "灯显信号确认": "signal",
    "启动": "engine",
    "启机": "engine",
    "前后近光灯": "light-front",
    "1端头灯": "light-front",
    "2端头灯": "light-front",
    "后头灯": "light-front",
    "短高音风笛": "horn-high",
    "短风笛1": "horn",
    "短风笛2": "horn",
    "注意进路": "signal",
    "蓝灯停车": "signal",
    "绿黄灯注意": "signal",
    "双黄灯侧线运行": "signal",
    "排气": "steam",
    "feed_pump": "water-pump",
    "混音鸣笛": "horn-mixed",
    "指挥哨": "horn",
    "隧道模式": "function-generic",
    "站台广播1": "announcement",
    "站台广播2": "announcement",
    "进站广播": "announcement",
    "车钩声": "coupler",
    "铲煤": "coal-shovel",
    "加煤": "coal-shovel",
    "加煤机": "coal-shovel",
    "scoop_coal": "coal-shovel",
    "scoop_coal_sound": "coal-shovel",
    "kohle_schaufeln": "coal-shovel",
    "preheat": "preheater",
    "气泵低速": "compressor",
    "puffer_kick": "sound-generic",
    "排污": "drain-valve",
    "drain_mud": "drain-valve",
    "hood_open": "hood",
    "hood_close": "hood",
    "all_round_light": "beacon-light",
    "rundumleuchte": "beacon-light",
    "车顶灯": "beacon-light",
    "标志灯": "beacon-light",
    "旋转警示灯": "beacon-light",
    "licence_plate_light": "number-board-light",
    "license_plate_light": "number-board-light",
    "nummernschild_light": "number-board-light",
    "车号灯": "number-board-light",
    "灯牌": "number-board-light",
    "前数字灯": "number-board-light",
    "数字灯": "number-board-light",
    "tish_lamp": "dashboard-light",
    "tischlampe": "dashboard-light",
    "仪表灯": "dashboard-light",
    "仪表台灯": "dashboard-light",
    "控制台灯": "dashboard-light",
    "1端仪表灯": "dashboard-light",
    "2端仪表灯": "dashboard-light",
    "rail_crossing": "rail-crossing",
    "道口信号": "rail-crossing",
    "叉道鸣笛": "rail-crossing",
    "brake_delay": "brake-delay",
    "惯性停车": "brake-delay",
    "延迟制动": "brake-delay",
    "车窗": "window-toggle",
    "车厢灯": "coach-light",
    "coach_light": "coach-light",
    "踏脚灯": "step-light",
    "脚踏灯": "step-light",
    "step_light": "step-light",
    "方向牌灯": "destination-sign",
    "路牌灯": "destination-sign",
    "手制动": "parking-brake",
    "parking_brake": "parking-brake",
    "抽水泵": "water-pump",
    "给水泵": "water-pump",
    "water_pump": "water-pump",
    "火箱": "firebox",
    "firebox": "firebox",
    "发电机": "generator",
    "内燃机预热": "preheater",
    "预热": "preheater",
    "引擎盖": "hood",
    "打开引擎盖": "hood",
    "关闭引擎盖": "hood",
    "转车台": "turntable",
    "向左旋转": "turntable",
    "向右旋转": "turntable",
    "turntable": "turntable",
    "重载": "load-mode",
    "升降货": "load-lift",
    "超重货上升": "load-lift",
    "超重货下降": "load-lift",
    "load_lift": "load-lift",
    "内燃机提速": "rpm-up",
    "rpm_up": "rpm-up",
    "内燃机减速": "rpm-down",
    "rpm_down": "rpm-down",
    "吊车": "crane",
    "crane": "crane",
    "Kran": "crane",
    "吊车左转": "crane-rotate-left",
    "吊臂左转": "crane-rotate-left",
    "crane_rotate_left": "crane-rotate-left",
    "吊车右转": "crane-rotate-right",
    "吊臂右转": "crane-rotate-right",
    "crane_rotate_right": "crane-rotate-right",
    "吊臂升": "crane-boom-up",
    "吊臂上升": "crane-boom-up",
    "crane_boom_up": "crane-boom-up",
    "吊臂降": "crane-boom-down",
    "吊臂下降": "crane-boom-down",
    "crane_boom_down": "crane-boom-down",
    "吊臂伸出": "crane-boom-extend",
    "伸臂": "crane-boom-extend",
    "crane_boom_extend": "crane-boom-extend",
    "吊臂缩回": "crane-boom-retract",
    "缩臂": "crane-boom-retract",
    "crane_boom_retract": "crane-boom-retract",
    "吊钩升": "crane-hook-up",
    "吊钩上升": "crane-hook-up",
    "crane_hook_up": "crane-hook-up",
    "吊钩降": "crane-hook-down",
    "吊钩下降": "crane-hook-down",
    "crane_hook_down": "crane-hook-down",
    "支腿": "crane-outrigger",
    "支撑": "crane-outrigger",
    "crane_outrigger": "crane-outrigger",
    "自由拖行": "crane-free-run",
    "Freilauf": "crane-free-run",
    "crane_free_run": "crane-free-run",
    "短鸣汽笛": "whistle-short",
    "长鸣汽笛": "whistle-long",
    "混合鸣笛": "horn-mixed"
  }
};

const VEHICLE_TYPE_LABELS = new Map([
  [0, "机车"],
  [1, "车厢"],
  [2, "附件"],
  [3, "重联/编组"],
  [4, "摄像车"]
]);

const VEHICLE_KIND_META = {
  diesel: {
    label: "内燃",
    iconText: "油",
    path: "assets/icons/vehicle-types/energy-diesel.svg"
  },
  electric: {
    label: "电力",
    iconText: "电",
    path: "assets/icons/vehicle-types/energy-electric.svg"
  },
  steam: {
    label: "蒸汽",
    iconText: "汽",
    path: "assets/icons/vehicle-types/energy-steam.svg"
  },
  hybrid: {
    label: "混动",
    iconText: "混",
    path: "assets/icons/vehicle-types/energy-hybrid.svg"
  },
  passenger: {
    label: "客车",
    iconText: "客",
    path: "assets/icons/vehicle-types/car-passenger.svg"
  },
  engineering: {
    label: "工程车",
    iconText: "工",
    path: "assets/icons/vehicle-types/car-engineering.svg"
  },
  inspection: {
    label: "检测车",
    iconText: "检",
    path: "assets/icons/vehicle-types/car-inspection.svg"
  },
  crane: {
    label: "起重机",
    iconText: "吊",
    path: "assets/icons/vehicle-types/car-crane.svg"
  },
  multiple_unit: {
    label: "重连机车",
    iconText: "重",
    path: "assets/icons/vehicle-types/consist-multiple-unit.svg"
  },
  powered_set: {
    label: "动集列车",
    iconText: "动",
    path: "assets/icons/vehicle-types/consist-powered-set.svg"
  },
  train_set: {
    label: "列车编组",
    iconText: "列",
    path: "assets/icons/vehicle-types/consist-train-set.svg"
  },
  consist: {
    label: "列车编组",
    iconText: "编",
    path: "assets/icons/vehicle-types/consist-group.svg"
  }
};

const VEHICLE_ENERGY_KIND_KEYS = new Set(["diesel", "electric", "steam", "hybrid"]);

function normalizeConsistKind(value) {
  const normalized = String(value || "").trim().toLowerCase();
  if (["multiple_unit", "powered_set", "train_set"].includes(normalized)) {
    return normalized;
  }
  return normalized === "consist" ? "train_set" : "multiple_unit";
}

let draggedVehicleRow = null;

export async function loadFunctionIconCatalog(fetchImpl = globalThis.fetch) {
  if (typeof fetchImpl !== "function") {
    return DEFAULT_FUNCTION_ICON_CATALOG;
  }
  try {
    const [catalogResponse, mappingResponse] = await Promise.all([
      fetchImpl("/config/function-icons.json", {cache: "no-store"}),
      fetchImpl("/config/function-icon-mappings/z21.json", {cache: "no-store"})
    ]);
    if (!catalogResponse.ok) {
      return DEFAULT_FUNCTION_ICON_CATALOG;
    }
    const catalog = await catalogResponse.json();
    const mapping = mappingResponse.ok ? await mappingResponse.json() : {};
    return catalog?.icons ? {...catalog, mappings: mapping.mappings || {}} : DEFAULT_FUNCTION_ICON_CATALOG;
  } catch (_error) {
    return DEFAULT_FUNCTION_ICON_CATALOG;
  }
}

export function renderVehicleRegistry(container, vehicles, handlers = {}) {
  container.replaceChildren();
  const header = document.createElement("div");
  header.className = "section-title";
  const count = document.createElement("span");
  count.textContent = `${vehicles.length} 辆`;
  header.append(count);

  const grid = document.createElement("div");
  grid.className = "vehicle-grid";
  for (const vehicle of vehicles) {
    const card = document.createElement("article");
    card.className = "vehicle-card";
    card.append(vehicleImage(vehicle), vehicleText(vehicle, handlers));
    const actions = document.createElement("div");
    actions.className = "card-actions";
    const edit = document.createElement("button");
    edit.type = "button";
    edit.textContent = "编辑";
    edit.addEventListener("click", () => handlers.onEdit?.(vehicle.id));
    const control = document.createElement("button");
    control.type = "button";
    control.textContent = "控制";
    control.addEventListener("click", () => handlers.onControl?.(vehicle.id));
    actions.append(edit, control);
    card.append(actions);
    grid.append(card);
  }
  if (!vehicles.length) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "暂无车辆";
    grid.append(empty);
  }
  container.append(header, grid);
}

export function renderVehicleControlWorkspace(container, vehicles, functions, cabState, handlers = {}) {
  const previousListScroll = captureCabVehicleListScroll(container);
  container.replaceChildren();

  if (!vehicles.length) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = handlers.emptyText || "暂无车辆，请先导入 Z21 配置";
    container.append(empty);
    return;
  }

  const workspace = document.createElement("div");
  workspace.className = "cab-workspace";
  const leftVehicles = handlers.cabVehicles?.left || vehicles;
  const rightVehicles = handlers.cabVehicles?.right || vehicles;
  workspace.append(
    renderCabColumn("left", "左控制台", leftVehicles, functions, cabState, handlers),
    renderCabColumn("right", "右控制台", rightVehicles, functions, cabState, handlers)
  );
  container.append(workspace);
  restoreCabVehicleListScroll(workspace, previousListScroll);
}

function captureCabVehicleListScroll(container) {
  const positions = {};
  for (const cabId of ["left", "right"]) {
    const list = container.querySelector(`.cab-column[data-cab-id="${cabId}"] .cab-vehicle-list`);
    if (list) {
      positions[cabId] = list.scrollTop;
    }
  }
  return positions;
}

function restoreCabVehicleListScroll(workspace, positions) {
  for (const [cabId, scrollTop] of Object.entries(positions)) {
    if (!Number.isFinite(scrollTop)) {
      continue;
    }
    const list = workspace.querySelector(`.cab-column[data-cab-id="${cabId}"] .cab-vehicle-list`);
    if (list) {
      list.scrollTop = scrollTop;
    }
  }
}

function renderCabColumn(cabId, titleText, vehicles, functions, cabState, handlers) {
  const cab = cabState.cabs?.[cabId] || {};
  const selectedVehicle = vehicles.find((vehicle) => vehicle.id === cab.vehicleId) || null;
  const showFunctionNumbers = cab.showFunctionNumbers !== false;
  const showFunctionLabels = cab.showFunctionLabels !== false;
  const section = document.createElement("section");
  section.className = `cab-column ${cabState.activeCabId === cabId ? "active-cab" : ""}`;
  section.dataset.cabId = cabId;
  section.addEventListener("pointerdown", (event) => {
    if (!isCabActivationTarget(event.target)) {
      return;
    }
    handlers.onActivateCab?.(cabId);
  });

  const header = document.createElement("div");
  header.className = "cab-header";
  const title = document.createElement("h2");
  title.textContent = titleText;
  const toggle = document.createElement("button");
  toggle.type = "button";
  toggle.className = "cab-toggle-control";
  toggle.textContent = cab.expanded ? "返回列表" : "展开控制";
  toggle.disabled = !selectedVehicle || !showFunctionLabels;
  toggle.title = showFunctionLabels ? "" : "隐藏功能名称时默认显示全部功能控制";
  toggle.addEventListener("click", (event) => {
    event.stopPropagation();
    handlers.onToggleCabExpanded?.(cabId);
  });
  const headerControls = document.createElement("div");
  headerControls.className = "cab-header-controls";
  headerControls.append(renderCabFilters(cabId, cab, handlers.categories || [], handlers), toggle);
  header.append(title, headerControls);

  section.append(header);
  const context = selectedVehicle ? resolveCabConsistContext(selectedVehicle, cab, functions, handlers) : null;
  const controlPanel = selectedVehicle ? renderCabControlPanel(cabId, selectedVehicle, cab, context.functions, handlers, {
    expanded: Boolean(cab.expanded && showFunctionLabels),
    showFunctionNumbers,
    showFunctionLabels,
    context,
    displayVehicle: context.displayVehicle,
    maxFunctionNumber: context.maxFunctionNumber
  }) : null;
  if (controlPanel) {
    section.append(controlPanel);
  }
  section.append(renderCabVehicleList(cabId, vehicles, cab, cabState, handlers));
  return section;
}

function renderCabFilters(cabId, cab, categories, handlers) {
  const bar = document.createElement("div");
  bar.className = "cab-filter-bar";
  const showFunctionNumbers = cab.showFunctionNumbers !== false;
  const showFunctionLabels = cab.showFunctionLabels !== false;

  const numberToggle = cabToggleButton({
    className: "cab-function-number-toggle",
    active: showFunctionNumbers,
    label: "显示功能编号",
    activeTitle: "功能键显示编号",
    inactiveTitle: "功能键隐藏编号",
    onClick: () => handlers.onToggleCabFunctionNumbers?.(cabId)
  });

  const nameToggle = cabToggleButton({
    className: "cab-function-label-toggle",
    active: showFunctionLabels,
    label: "显示功能名称",
    activeTitle: "功能键显示名称",
    inactiveTitle: "功能键只显示编号和图标",
    onClick: () => handlers.onToggleCabFunctionLabels?.(cabId)
  });

  const category = document.createElement("select");
  category.append(option("", "全部分类"));
  for (const item of categories) {
    category.append(option(item.id, item.name));
  }
  category.value = String(cab.categoryId || "");
  category.addEventListener("change", () => handlers.onCabCategoryFilter?.(cabId, category.value));

  const sort = document.createElement("select");
  for (const [value, label] of [["custom", "自定义排序"], ["created_at", "添加时间"], ["address", "车辆号"], ["name", "车辆名称"], ["railway", "局段"]]) {
    sort.append(option(value, label));
  }
  sort.value = cab.sortKey || "custom";
  sort.addEventListener("change", () => handlers.onCabSortChange?.(cabId, sort.value, cab.sortDirection || "asc"));

  const direction = document.createElement("button");
  direction.type = "button";
  direction.textContent = cab.sortDirection === "desc" ? "降序" : "升序";
  direction.addEventListener("click", () => {
    handlers.onCabSortChange?.(cabId, cab.sortKey || "custom", cab.sortDirection === "desc" ? "asc" : "desc");
  });

  bar.append(numberToggle, nameToggle, category, sort, direction);
  return bar;
}

function cabToggleButton({className, active, label, activeTitle, inactiveTitle, onClick}) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = className;
  button.classList.toggle("active", active);
  button.textContent = label;
  button.setAttribute("aria-pressed", active ? "true" : "false");
  button.title = active ? activeTitle : inactiveTitle;
  button.addEventListener("click", onClick);
  return button;
}

function option(value, label) {
  const item = document.createElement("option");
  item.value = value;
  item.textContent = label;
  return item;
}

function renderCabVehicleList(cabId, vehicles, cab, cabState, handlers) {
  const list = document.createElement("div");
  list.className = "cab-vehicle-list";
  list.addEventListener("dragover", (event) => {
    const targetRow = event.target?.closest?.(".cab-vehicle-row");
    if (!targetRow || targetRow === draggedVehicleRow) {
      return;
    }
    event.preventDefault();
    renderDragInsertionPreview(list, targetRow, event);
    handlers.onVehicleDragOver?.(cabId, targetRow.dataset.vehicleId, event);
  });
  list.addEventListener("drop", (event) => {
    const targetRow = event.target?.closest?.(".cab-vehicle-row");
    if (!targetRow && !draggedVehicleRow) {
      return;
    }
    event.preventDefault();
    const vehicleId = targetRow?.dataset.vehicleId || draggedVehicleRow?.dataset.vehicleId || "";
    const orderedVehicleIds = orderedVehicleIdsFromList(list);
    handlers.onVehicleDrop?.(cabId, vehicleId, event, orderedVehicleIds);
    clearDragPreview();
  });
  for (const vehicle of vehicles) {
    const isSelected = cab.vehicleId === vehicle.id;
    const isMultiSelected = handlers.selectedVehicleIds?.has?.(vehicle.id) || false;
    const selectionMode = Boolean(handlers.selectionMode);
    const disabledByOtherCab = selectedByOtherCab(cabId, cabState, vehicle.id);
    const row = document.createElement("div");
    row.className = `cab-vehicle-row ${isSelected ? "selected" : ""}`;
    row.dataset.vehicleId = String(vehicle.id);
    row.draggable = true;
    row.classList.toggle("multi-selected", isMultiSelected);
    row.classList.toggle("disabled-by-other-cab", disabledByOtherCab && !selectionMode);
    row.setAttribute("aria-disabled", disabledByOtherCab && !selectionMode ? "true" : "false");
    row.addEventListener("click", () => {
      if (selectionMode) {
        handlers.onToggleVehicleSelection?.(vehicle.id);
        return;
      }
      if (disabledByOtherCab) {
        return;
      }
      handlers.onSelectVehicle?.(cabId, vehicle.id);
    });
    if (selectionMode) {
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.className = "vehicle-multi-select";
      checkbox.checked = isMultiSelected;
      checkbox.addEventListener("click", (event) => {
        event.stopPropagation();
        handlers.onToggleVehicleSelection?.(vehicle.id);
      });
      row.append(checkbox);
    }
    const select = document.createElement("button");
    select.type = "button";
    select.className = "cab-vehicle-select";
    select.disabled = disabledByOtherCab && !selectionMode;
    select.setAttribute("aria-disabled", disabledByOtherCab && !selectionMode ? "true" : "false");
    select.setAttribute("aria-pressed", isSelected ? "true" : "false");
    select.title = `选择 ${vehicle.name || "未命名车辆"} 作为${cabId === "left" ? "左控制台" : "右控制台"}当前控制车辆`;
    select.append(vehicleImage(vehicle), vehicleText(vehicle, handlers));
    select.addEventListener("click", (event) => {
      event.stopPropagation();
      if (selectionMode) {
        handlers.onToggleVehicleSelection?.(vehicle.id);
        return;
      }
      if (disabledByOtherCab) {
        return;
      }
      handlers.onSelectVehicle?.(cabId, vehicle.id);
    });
    const statusSlot = document.createElement("span");
    statusSlot.className = "cab-current-badge-slot";
    if (isSelected) {
      const badge = document.createElement("span");
      badge.className = "cab-current-badge";
      badge.textContent = "当前控制";
      statusSlot.append(badge);
    }
    if (disabledByOtherCab) {
      const disabledBadge = document.createElement("span");
      disabledBadge.className = "cab-disabled-badge";
      disabledBadge.textContent = "另一侧已选";
      select.append(disabledBadge);
    }
    const edit = document.createElement("button");
    edit.type = "button";
    edit.className = "cab-vehicle-edit";
    edit.textContent = "编辑";
    edit.addEventListener("click", (event) => {
      event.stopPropagation();
      handlers.onEdit?.(vehicle.id);
    });
    const drag = document.createElement("button");
    drag.type = "button";
    drag.className = "vehicle-drag-handle";
    drag.draggable = true;
    drag.title = "拖动调整自定义排序";
    drag.textContent = "☰";
    drag.addEventListener("click", (event) => event.stopPropagation());
    drag.addEventListener("pointerdown", (event) => event.stopPropagation());
    row.addEventListener("dragstart", (event) => {
      if (disabledByOtherCab) {
        event.preventDefault();
        return;
      }
      draggedVehicleRow = row;
      row.classList.add("dragging");
      event.dataTransfer?.setData("text/plain", vehicle.id);
      if (event.dataTransfer) {
        event.dataTransfer.effectAllowed = "move";
      }
      handlers.onVehicleDragStart?.(cabId, vehicle.id, event);
    });
    row.addEventListener("dragend", clearDragPreview);
    row.append(select, statusSlot, edit, drag);
    list.append(row);
  }
  return list;
}

function isCabActivationTarget(target) {
  return !target?.closest?.("button, input, select, textarea, label, .cab-vehicle-row, .cab-control-panel, .cab-filter-bar");
}

function renderDragInsertionPreview(list, targetRow, event) {
  if (!draggedVehicleRow || targetRow === draggedVehicleRow) {
    return;
  }
  const rect = targetRow.getBoundingClientRect();
  const insertAfter = event.clientY > rect.top + rect.height / 2;
  list.insertBefore(draggedVehicleRow, insertAfter ? targetRow.nextSibling : targetRow);
}

function orderedVehicleIdsFromList(list) {
  return Array.from(list.querySelectorAll(".cab-vehicle-row"))
    .map((row) => row.dataset.vehicleId)
    .filter(Boolean);
}

function clearDragPreview() {
  draggedVehicleRow?.classList.remove("dragging");
  draggedVehicleRow = null;
}

function resolveCabConsistContext(selectedVehicle, cab, functions, handlers) {
  const base = {
    controlVehicle: selectedVehicle,
    displayVehicle: selectedVehicle,
    functionVehicle: selectedVehicle,
    functions: vehicleFunctions(functions, selectedVehicle.id),
    consist: null,
    members: [],
    memberIndex: null,
    maxFunctionNumber: cab.showFunctionLabels === false ? 31 : 9
  };
  if (Number(selectedVehicle.type ?? 0) !== 3) {
    return base;
  }
  const consist = findConsistForVehicle(selectedVehicle.id, handlers.consists || []);
  const members = sortedConsistMembers(consist, handlers.vehicles || []);
  base.consist = consist;
  base.members = members;
  if (selectedVehicle.sync_function_control) {
    return base;
  }
  const memberIndex = Number.isInteger(cab.memberIndex) ? cab.memberIndex : null;
  const member = memberIndex === null ? null : members[memberIndex] || null;
  if (!member) {
    return {
      ...base,
      functions: [{function_number: 0, label: "", icon_name: "function-generic", is_configured: true, position: 0}],
      memberIndex: null,
      maxFunctionNumber: 0
    };
  }
  return {
    ...base,
    displayVehicle: member.vehicle,
    functionVehicle: member.vehicle,
    functions: vehicleFunctions(functions, member.vehicle.id),
    memberIndex
  };
}

function renderConsistImageSwitcher(cabId, image, context, handlers) {
  if (!context?.consist || context.controlVehicle?.sync_function_control || !context.members?.length) {
    return image;
  }
  const switcher = document.createElement("div");
  switcher.className = "cab-consist-image-switcher";
  const previous = document.createElement("button");
  previous.type = "button";
  previous.textContent = "‹";
  previous.title = "上一台成员车";
  previous.addEventListener("click", () => handlers.onSwitchConsistMember?.(cabId, -1));
  const next = document.createElement("button");
  next.type = "button";
  next.textContent = "›";
  next.title = "下一台成员车";
  next.addEventListener("click", () => handlers.onSwitchConsistMember?.(cabId, 1));
  switcher.append(previous, image, next);
  return switcher;
}

function renderCabControlPanel(cabId, vehicle, cab, functions, handlers, options = {}) {
  const panel = document.createElement("section");
  panel.className = "cab-control-panel";
  const showFunctionNumbers = options.showFunctionNumbers !== false;
  const showFunctionLabels = options.showFunctionLabels !== false;
  const displayVehicle = options.displayVehicle || vehicle;
  const context = options.context || {};

  const mainRow = document.createElement("div");
  mainRow.className = "cab-control-main-row";

  const identity = document.createElement("div");
  identity.className = "cab-control-identity";
  const nameLine = document.createElement("strong");
  nameLine.className = "cab-control-identity-line cab-control-identity-primary cab-control-vehicle-name";
  nameLine.textContent = vehicle.name || "未命名车辆";
  const addressLine = document.createElement("span");
  addressLine.className = "cab-control-identity-line cab-control-address-row";
  const addressBadge = document.createElement("span");
  addressBadge.className = "cab-control-address-badge";
  addressBadge.textContent = formatCabAddressText(vehicle, context);
  const fullNameTag = cabControlInfoTag(formatVehicleField(vehicle.full_name), "cab-control-full-name-tag", "完整名称");
  addressLine.append(addressBadge, fullNameTag);
  const metaLine = document.createElement("span");
  metaLine.className = "cab-control-identity-line cab-control-meta-row";
  const brandTag = cabControlInfoTag(formatVehicleField(vehicle.brand), "cab-control-meta-tag", "品牌");
  const articleNumberTag = cabControlInfoTag(formatVehicleField(vehicle.article_number), "cab-control-meta-tag", "货号");
  metaLine.append(brandTag, articleNumberTag);

  const media = document.createElement("div");
  media.className = "cab-control-media";
  const image = document.createElement("div");
  image.className = "cab-control-image";
  image.append(vehicleImage(displayVehicle));

  const speed = Number(cab.speed || 0);
  const speedControl = document.createElement("div");
  speedControl.className = "cab-speed-control";
  const speedValue = document.createElement("strong");
  speedValue.className = "cab-speed-value";
  speedValue.textContent = formatCabSpeedValue(speed, vehicle.max_speed);
  const throttle = document.createElement("div");
  throttle.className = "cab-speed-throttle";
  throttle.tabIndex = 0;
  throttle.setAttribute("role", "slider");
  throttle.setAttribute("aria-label", "速度");
  throttle.setAttribute("aria-valuemin", "0");
  throttle.setAttribute("aria-valuemax", "126");
  const throttleFill = document.createElement("div");
  throttleFill.className = "cab-speed-throttle-fill";
  throttle.append(throttleFill);
  let pendingSpeed = speed;
  let isDraggingThrottle = false;
  updateCabSpeedThrottleFill(throttle, speed);
  const previewThrottleSpeed = (nextSpeed) => {
    pendingSpeed = clampCabSpeedStep(nextSpeed);
    updateCabSpeedThrottleFill(throttle, pendingSpeed);
    speedValue.textContent = formatCabSpeedValue(pendingSpeed, vehicle.max_speed);
    handlers.onSpeedPreview?.(cabId, pendingSpeed, cab.direction || "forward");
  };
  const commitThrottleSpeed = (nextSpeed) => {
    pendingSpeed = clampCabSpeedStep(nextSpeed);
    updateCabSpeedThrottleFill(throttle, pendingSpeed);
    speedValue.textContent = formatCabSpeedValue(pendingSpeed, vehicle.max_speed);
    handlers.onSpeed?.(cabId, pendingSpeed, cab.direction || "forward");
  };
  const updateFromPointer = (event, commit = false) => {
    const nextSpeed = speedFromThrottlePointer(throttle, event);
    if (commit) {
      commitThrottleSpeed(nextSpeed);
      return;
    }
    previewThrottleSpeed(nextSpeed);
  };
  throttle.addEventListener("pointerdown", (event) => {
    event.preventDefault();
    handlers.onActivateCab?.(cabId, {render: false});
    throttle.focus({preventScroll: true});
    isDraggingThrottle = true;
    throttle.setPointerCapture?.(event.pointerId);
    updateFromPointer(event);
  });
  throttle.addEventListener("pointermove", (event) => {
    if (!isDraggingThrottle) {
      return;
    }
    event.preventDefault();
    updateFromPointer(event);
  });
  throttle.addEventListener("pointerup", (event) => {
    if (!isDraggingThrottle) {
      return;
    }
    event.preventDefault();
    isDraggingThrottle = false;
    throttle.releasePointerCapture?.(event.pointerId);
    updateFromPointer(event, true);
  });
  throttle.addEventListener("pointercancel", (event) => {
    if (!isDraggingThrottle) {
      return;
    }
    isDraggingThrottle = false;
    throttle.releasePointerCapture?.(event.pointerId);
    commitThrottleSpeed(pendingSpeed);
  });
  throttle.addEventListener("keydown", (event) => {
    const keySteps = {
      ArrowUp: 1,
      ArrowRight: 1,
      PageUp: 10,
      ArrowDown: -1,
      ArrowLeft: -1,
      PageDown: -10
    };
    if (event.key === "Home") {
      event.preventDefault();
      event.stopPropagation();
      commitThrottleSpeed(0);
      return;
    }
    if (event.key === "End") {
      event.preventDefault();
      event.stopPropagation();
      commitThrottleSpeed(126);
      return;
    }
    if (!(event.key in keySteps)) {
      return;
    }
    event.preventDefault();
    event.stopPropagation();
    commitThrottleSpeed(pendingSpeed + keySteps[event.key]);
  });
  speedControl.append(speedValue, throttle);
  identity.append(nameLine, addressLine, metaLine);
  media.append(renderConsistImageSwitcher(cabId, image, context, handlers));

  const infoColumn = document.createElement("div");
  infoColumn.className = "cab-control-info";
  infoColumn.append(identity);

  const functionGrid = document.createElement("div");
  functionGrid.className = `function-grid cab-function-grid ${showFunctionLabels ? "show-function-labels" : "show-all-functions hide-function-labels"}`;
  functionGrid.dataset.showFunctionLabels = showFunctionLabels ? "true" : "false";
  const functionIconCatalog = handlers.functionIconCatalog || DEFAULT_FUNCTION_ICON_CATALOG;
  const slotOptions = {maxFunctionNumber: showFunctionLabels ? 9 : 31};
  if (Number.isFinite(options.maxFunctionNumber)) {
    slotOptions.maxFunctionNumber = options.maxFunctionNumber;
  }
  for (const fn of buildFunctionSlots(functions, slotOptions.maxFunctionNumber)) {
    if (fn.visible === false) {
      functionGrid.append(renderEmptyFunctionSlot(fn.function_number));
      continue;
    }
    functionGrid.append(renderFunctionSlotButton(
      fn,
      resolveFunctionIcon(fn, functionIconCatalog),
      (eventType) => handlers.onFunction?.(cabId, fn.function_number, eventType),
      {enabled: cab.functions?.[String(fn.function_number)], showLabel: showFunctionLabels, showNumber: showFunctionNumbers}
    ));
  }

  const reverse = segmentButton("←", cab.direction === "reverse", () => handlers.onDirection?.(cabId, "reverse"));
  reverse.title = "后退";
  reverse.setAttribute("aria-label", "后退");
  const forward = segmentButton("→", cab.direction !== "reverse", () => handlers.onDirection?.(cabId, "forward"));
  forward.title = "前进";
  forward.setAttribute("aria-label", "前进");
  const directionRow = document.createElement("div");
  directionRow.className = "cab-direction-row";
  directionRow.append(reverse, forward);

  const stop = document.createElement("button");
  stop.type = "button";
  stop.className = "danger cab-economic-stop";
  stop.textContent = "紧急停车";
  stop.addEventListener("click", () => handlers.onEmergencyStop?.(cabId));
  const sideActions = document.createElement("div");
  sideActions.className = "cab-control-side-actions";
  sideActions.append(speedControl, directionRow, stop);
  mainRow.append(infoColumn, media, functionGrid, sideActions);

  panel.append(mainRow);
  if (options.expanded && showFunctionLabels) {
    const extraGrid = document.createElement("div");
    extraGrid.className = "function-grid function-extra-grid";
    for (const fn of buildExpandedFunctionSlots(functions)) {
      if (fn.visible === false) {
        extraGrid.append(renderEmptyFunctionSlot(fn.function_number));
        continue;
      }
      extraGrid.append(renderFunctionSlotButton(
        fn,
        resolveFunctionIcon(fn, functionIconCatalog),
        (eventType) => handlers.onFunction?.(cabId, fn.function_number, eventType),
        {enabled: cab.functions?.[String(fn.function_number)], showLabel: true, showNumber: showFunctionNumbers}
      ));
    }
    if (extraGrid.childElementCount) {
      panel.append(extraGrid);
    }
  }
  return panel;
}

function formatCabSpeedValue(speedStep, maxSpeed) {
  const step = clampCabSpeedStep(speedStep);
  if (Number(maxSpeed) > 0) {
    const scaled = Math.round((step / 126) * Number(maxSpeed));
    return `${scaled} km/h`;
  }
  return String(step);
}

function cabControlInfoTag(valueText, className, labelText) {
  const tag = document.createElement("span");
  tag.className = className;
  tag.dataset.label = labelText;
  tag.textContent = labelText === "完整名称" ? valueText : `${labelText} ${valueText}`;
  tag.title = `${labelText} ${valueText}`;
  tag.setAttribute("aria-label", `${labelText} ${valueText}`);
  return tag;
}

function clampCabSpeedStep(speedStep) {
  return Math.max(0, Math.min(126, Math.round(Number(speedStep || 0))));
}

function updateCabSpeedThrottleFill(throttle, speedStep) {
  const step = clampCabSpeedStep(speedStep);
  const percent = Math.round((step / 126) * 1000) / 10;
  throttle.style.setProperty("--speed-fill-percent", `${percent}%`);
  throttle.setAttribute("aria-valuenow", String(step));
}

function speedFromThrottlePointer(throttle, event) {
  const rect = throttle.getBoundingClientRect();
  if (!rect.height) {
    return 0;
  }
  const ratio = (rect.bottom - event.clientY) / rect.height;
  return clampCabSpeedStep(ratio * 126);
}

function formatCabAddressText(vehicle, context = {}) {
  if (Number(vehicle?.type ?? 0) === 3 && context.consist) {
    if (context.memberIndex !== null && context.displayVehicle) {
      return String(context.displayVehicle.address || "--");
    }
    const addresses = (context.members || [])
      .map((member) => member.address || member.vehicle?.address)
      .filter((address) => address !== null && address !== undefined && String(address).trim() !== "")
      .map((address) => String(address));
    return addresses.slice(0, 3).join("|") || "--";
  }
  return String(vehicle?.address || "--");
}

export function renderVehicleEditor(container, vehicle, functions, handlers = {}) {
  container.replaceChildren();
  if (!vehicle) {
    container.hidden = true;
    return;
  }
  if (Number(vehicle.type ?? 0) === 3) {
    renderConsistVehicleEditor(container, vehicle, functions, handlers);
    return;
  }
  container.hidden = false;
  const toolbar = subviewToolbar("车辆编辑", handlers.onBack);
  const basicInfo = document.createElement("div");
  basicInfo.className = "vehicle-editor-basic-info";
  const preview = renderVehicleImageUploader(vehicle, handlers);

  const name = inputField("车辆名称", "text", vehicle.name || "");
  const address = inputField("车辆编号", "number", vehicle.address || 3, {min: 1, max: 9999});
  const fullName = inputField("完整名称", "text", vehicle.full_name || "");
  const scale = selectField("比例", vehicle.track_mode || "ho", [["ho", "HO"], ["n", "N"]]);
  const vehicleType = selectField("车辆类型", String(vehicle.type ?? 0), vehicleTypeOptions());
  const energyType = renderVehicleKindChoiceField("能源类型", vehicle.energy_type || "electric", ["diesel", "electric", "steam", "hybrid"]);
  const carSubtype = renderVehicleKindChoiceField("车厢子类", vehicle.car_subtype || "passenger", ["passenger", "engineering", "inspection", "crane"]);
  const brand = inputField("模型品牌", "text", vehicle.brand || "");
  const maxSpeed = inputField("最高速度 km/h", "number", vehicle.max_speed || "", {min: 0, max: 999});
  const railway = inputField("铁路公司/局段", "text", vehicle.railway || "");
  const articleNumber = inputField("货号", "text", vehicle.article_number || "");
  const decoderType = inputField("芯片型号", "text", vehicle.decoder_type || "");
  const description = inputField("备注", "text", vehicle.description || "");
  const railwayOptions = createVehicleValueDatalist("vehicle-railway-options", handlers.railwayOptions || []);
  const decoderTypeOptions = createVehicleValueDatalist("vehicle-decoder-type-options", handlers.decoderTypeOptions || []);
  railway.input.setAttribute("list", "vehicle-railway-options");
  decoderType.input.setAttribute("list", "vehicle-decoder-type-options");
  name.label.classList.add("vehicle-field-name");
  fullName.label.classList.add("vehicle-field-full-name");
  scale.label.classList.add("vehicle-field-scale");
  vehicleType.label.classList.add("vehicle-field-type");
  energyType.label.classList.add("vehicle-kind-field", "vehicle-energy-field");
  carSubtype.label.classList.add("vehicle-kind-field", "vehicle-car-subtype-field");
  brand.label.classList.add("vehicle-field-brand");
  maxSpeed.label.classList.add("vehicle-field-max-speed");
  address.label.classList.add("vehicle-field-address");
  railway.label.classList.add("vehicle-field-railway");
  articleNumber.label.classList.add("vehicle-field-article-number");
  decoderType.label.classList.add("vehicle-field-decoder-type");
  const kindDynamicFields = document.createElement("div");
  kindDynamicFields.className = "vehicle-kind-dynamic-fields";
  const updateKindFieldVisibility = () => {
    const selectedType = Number(vehicleType.input.value);
    kindDynamicFields.replaceChildren();
    if (selectedType === 0) {
      energyType.input.disabled = false;
      carSubtype.input.disabled = true;
      kindDynamicFields.append(energyType.label);
    } else if (selectedType === 1) {
      energyType.input.disabled = true;
      carSubtype.input.disabled = false;
      kindDynamicFields.append(carSubtype.label);
    } else {
      energyType.input.disabled = true;
      carSubtype.input.disabled = true;
    }
    kindDynamicFields.hidden = kindDynamicFields.childElementCount === 0;
  };
  vehicleType.input.addEventListener("change", () => {
    updateKindFieldVisibility();
    handlers.onTypeChange?.(Number(vehicleType.input.value));
  });

  const nameRow = document.createElement("div");
  nameRow.className = "vehicle-editor-name-row";
  nameRow.append(name.label, fullName.label);
  const kindRow = document.createElement("div");
  kindRow.className = "vehicle-editor-kind-row";
  kindRow.append(vehicleType.label, kindDynamicFields);
  const runningRow = document.createElement("div");
  runningRow.className = "vehicle-editor-running-row";
  runningRow.append(address.label, scale.label, maxSpeed.label, railway.label);
  const modelRow = document.createElement("div");
  modelRow.className = "vehicle-editor-model-row";
  modelRow.append(brand.label, articleNumber.label, decoderType.label);
  const categoryEditor = renderCategoryEditor(vehicle, handlers.categories || []);
  basicInfo.append(
    nameRow,
    kindRow,
    runningRow,
    modelRow,
    description.label,
    categoryEditor
  );
  updateKindFieldVisibility();

  const functionEditor = renderFunctionTable(functions, handlers.functionIconCatalog || DEFAULT_FUNCTION_ICON_CATALOG);
  const actionRow = renderVehicleEditorActionRow(handlers);
  const {form} = renderVehicleEditorLayout({
    toolbar,
    preview,
    basicInfo,
    functionPanel: functionEditor,
    actionRow,
    formClassName: "stack-form vehicle-editor-form",
    leadingContent: [railwayOptions, decoderTypeOptions]
  });
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    handlers.onSave?.({
      name: name.input.value.trim(),
      address: Number(address.input.value),
      full_name: fullName.input.value.trim(),
      track_mode: scale.input.value,
      type: Number(vehicleType.input.value),
      sync_function_control: false,
      energy_type: Number(vehicleType.input.value) === 0 ? energyType.input.value : "",
      car_subtype: Number(vehicleType.input.value) === 1 ? carSubtype.input.value : "",
      brand: brand.input.value.trim(),
      max_speed: Number(maxSpeed.input.value || 0) || null,
      railway: railway.input.value.trim(),
      article_number: articleNumber.input.value.trim(),
      decoder_type: decoderType.input.value.trim(),
      description: description.input.value.trim(),
      image_path: vehicle.image_path || "",
      category_ids: collectCategoryIds(categoryEditor),
      functions: collectFunctions(functionEditor)
    });
  });

  container.append(toolbar, form);
}

function renderConsistVehicleEditor(container, vehicle, functions, handlers = {}) {
  container.hidden = false;
  const toolbar = subviewToolbar("重联/编组编辑", handlers.onBack);
  const basicInfo = document.createElement("div");
  basicInfo.className = "vehicle-editor-basic-info vehicle-consist-basic-info";
  const preview = renderVehicleImageUploader(vehicle, handlers);
  const existingConsist = findConsistForVehicle(vehicle.id, handlers.consists || []);
  const name = inputField("编组名称", "text", vehicle.name || existingConsist?.name || "");
  const scale = selectField("比例", vehicle.track_mode || "ho", [["ho", "HO"], ["n", "N"]]);
  const consistKind = renderConsistKindChoiceField(vehicle.consist_kind || existingConsist?.consist_kind || "multiple_unit");
  const syncFunctionControl = checkboxField("同步控制功能", Boolean(vehicle.sync_function_control));
  syncFunctionControl.label.classList.add("sync-toggle-inline");
  name.label.classList.add("vehicle-field-name");
  scale.label.classList.add("vehicle-field-scale");
  const categoryEditor = renderCategoryEditor(vehicle, handlers.categories || []);
  const memberEditor = renderConsistMemberEditor(existingConsist, vehicle, handlers.vehicles || []);

  const functionPanel = document.createElement("div");
  functionPanel.className = "vehicle-consist-function-panel";
  let functionEditor = renderFunctionTable(functions, handlers.functionIconCatalog || DEFAULT_FUNCTION_ICON_CATALOG);
  const syncFirstMember = document.createElement("button");
  syncFirstMember.type = "button";
  syncFirstMember.textContent = "同步编组内第一台车功能表";
  syncFirstMember.addEventListener("click", () => {
    const firstMember = collectConsistMembers(memberEditor)[0];
    if (!firstMember) {
      return;
    }
    const firstFunctions = functionsForVehicle(handlers.functionsByVehicle, firstMember.vehicle_id);
    functionEditor = renderFunctionTable(firstFunctions, handlers.functionIconCatalog || DEFAULT_FUNCTION_ICON_CATALOG);
    functionPanel.replaceChildren(syncFirstMember, functionEditor);
  });
  functionPanel.append(syncFirstMember, functionEditor);

  const updateConsistFormState = () => {
    functionPanel.hidden = !syncFunctionControl.input.checked;
  };
  syncFunctionControl.input.addEventListener("change", updateConsistFormState);
  memberEditor.addEventListener("change", updateConsistFormState);
  memberEditor.addEventListener("click", () => globalThis.setTimeout(updateConsistFormState, 0));
  updateConsistFormState();

  const actionRow = renderVehicleEditorActionRow(handlers);

  const consistNameRow = document.createElement("div");
  consistNameRow.className = "vehicle-editor-name-row vehicle-consist-name-row";
  consistNameRow.append(name.label, scale.label, syncFunctionControl.label);
  const consistKindRow = document.createElement("div");
  consistKindRow.className = "vehicle-editor-kind-row vehicle-consist-kind-row";
  consistKindRow.append(consistKind.label);
  basicInfo.append(
    consistNameRow,
    consistKindRow,
    categoryEditor,
    memberEditor
  );
  const {form} = renderVehicleEditorLayout({
    toolbar,
    preview,
    basicInfo,
    functionPanel,
    actionRow,
    formClassName: "stack-form vehicle-consist-editor",
    layoutClassName: "vehicle-consist-editor-layout",
    leftColumnClassName: "vehicle-editor-left-column vehicle-consist-editor-left-column",
    functionColumnClassName: "vehicle-editor-function-column vehicle-consist-editor-function-column"
  });
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const members = collectConsistMembers(memberEditor);
    handlers.onSave?.({
      name: name.input.value.trim(),
      address: Number(vehicle.address || 3),
      full_name: "",
      track_mode: scale.input.value,
      type: 3,
      sync_function_control: syncFunctionControl.input.checked,
      energy_type: "",
      car_subtype: "",
      consist_kind: consistKind.input.value,
      max_speed: null,
      railway: "",
      article_number: "",
      decoder_type: "",
      description: "",
      image_path: vehicle.image_path || "",
      category_ids: collectCategoryIds(categoryEditor),
      functions: syncFunctionControl.input.checked ? collectFunctions(functionEditor) : [],
      consist_members: collectConsistMembers(memberEditor),
      consist: {
        id: existingConsist?.id || "",
        name: name.input.value.trim(),
        track_mode: scale.input.value,
        consist_kind: consistKind.input.value,
        members
      }
    });
  });
  container.append(toolbar, form);
}

function renderVehicleEditorLayout({
  toolbar,
  preview,
  basicInfo,
  functionPanel,
  actionRow,
  leadingContent = [],
  formClassName = "stack-form vehicle-editor-form",
  layoutClassName = "vehicle-editor-layout",
  leftColumnClassName = "vehicle-editor-left-column",
  functionColumnClassName = "vehicle-editor-function-column"
}) {
  const form = document.createElement("form");
  form.className = formClassName;
  const layout = document.createElement("div");
  layout.className = `editor-layout ${layoutClassName}`;
  const leftColumn = document.createElement("div");
  leftColumn.className = leftColumnClassName;
  const functionColumn = document.createElement("section");
  functionColumn.className = functionColumnClassName;
  leftColumn.append(preview, basicInfo, actionRow);
  functionColumn.append(functionPanel);
  layout.append(leftColumn, functionColumn);
  form.append(...leadingContent, layout);
  return {toolbar, form, layout, leftColumn, functionColumn};
}

function renderVehicleEditorActionRow(handlers = {}) {
  const actionRow = document.createElement("div");
  actionRow.className = "vehicle-editor-actions";
  const save = document.createElement("button");
  save.type = "submit";
  save.textContent = "保存车辆";
  const deleteVehicleButton = document.createElement("button");
  deleteVehicleButton.type = "button";
  deleteVehicleButton.className = "danger";
  deleteVehicleButton.textContent = handlers.isNew ? "取消" : "删除车辆";
  deleteVehicleButton.addEventListener("click", () => handlers.onDelete?.());
  actionRow.append(save, deleteVehicleButton);
  return actionRow;
}

function renderConsistMemberEditor(consist, controlVehicle, vehicles) {
  const fieldset = document.createElement("fieldset");
  fieldset.className = "vehicle-consist-member-list";
  const legend = document.createElement("legend");
  legend.textContent = "编组成员";
  const rows = document.createElement("div");
  rows.className = "vehicle-consist-member-rows";
  const availableVehicles = vehicles.filter((vehicle) => {
    return String(vehicle.id) !== String(controlVehicle.id)
      && Number(vehicle.type ?? 0) !== 3
      && String(vehicle.track_mode || "").toLowerCase() === String(controlVehicle.track_mode || "").toLowerCase();
  });
  const appendRow = (member = {}) => {
    const row = document.createElement("div");
    row.className = "vehicle-consist-member-row";
    const vehicleSelect = document.createElement("select");
    vehicleSelect.className = "vehicle-consist-member-select";
    vehicleSelect.dataset.pendingValue = String(member.vehicle_id || "");
    const thumb = renderConsistMemberImage(member.vehicle_id, availableVehicles);
    vehicleSelect.addEventListener("change", () => {
      updateConsistMemberImage(thumb, vehicleSelect.value, availableVehicles);
      refreshConsistMemberOptions(rows, availableVehicles);
      fieldset.dispatchEvent(new Event("change", {bubbles: true}));
    });
    const reverse = toggleButtonField("反转运行", member.direction === "reverse");
    reverse.button.addEventListener("click", () => fieldset.dispatchEvent(new Event("change", {bubbles: true})));
    const remove = document.createElement("button");
    remove.type = "button";
    remove.textContent = "移除";
    remove.addEventListener("click", () => {
      row.remove();
      refreshConsistMemberOptions(rows, availableVehicles);
      fieldset.dispatchEvent(new Event("change", {bubbles: true}));
    });
    row.append(thumb, vehicleSelect, reverse.button, remove);
    rows.append(row);
    refreshConsistMemberOptions(rows, availableVehicles);
  };
  for (const member of consist?.members || []) {
    appendRow(member);
  }
  const add = document.createElement("button");
  add.type = "button";
  add.textContent = "添加车辆";
  add.addEventListener("click", () => {
    appendRow();
    refreshConsistMemberOptions(rows, availableVehicles);
    fieldset.dispatchEvent(new Event("change", {bubbles: true}));
  });
  if (!rows.childElementCount) {
    appendRow();
  }
  fieldset.append(legend, rows, add);
  return fieldset;
}

function refreshConsistMemberOptions(rows, availableVehicles) {
  const selects = Array.from(rows.querySelectorAll(".vehicle-consist-member-select"));
  const selectedVehicleIds = new Set(selects.map((select) => select.value || select.dataset.pendingValue || "").filter(Boolean));
  for (const select of selects) {
    const currentValue = select.value || select.dataset.pendingValue || "";
    select.replaceChildren(option("", "选择车辆"));
    for (const candidate of availableVehicles) {
      const candidateId = String(candidate.id);
      if (selectedVehicleIds.has(candidateId) && candidateId !== currentValue) {
        continue;
      }
      select.append(option(candidateId, renderConsistMemberOptionLabel(candidate)));
    }
    select.value = currentValue;
    select.dataset.pendingValue = "";
  }
}

function renderConsistMemberOptionLabel(vehicle) {
  return `${vehicle.name || vehicle.address} / ${vehicle.address || "-"}`;
}

function renderConsistMemberImage(vehicleId, availableVehicles) {
  const thumb = document.createElement("span");
  thumb.className = "vehicle-consist-member-thumb";
  updateConsistMemberImage(thumb, vehicleId, availableVehicles);
  return thumb;
}

function updateConsistMemberImage(thumb, vehicleId, availableVehicles) {
  const vehicle = (availableVehicles || []).find((candidate) => String(candidate.id) === String(vehicleId || ""));
  thumb.replaceChildren();
  if (vehicle) {
    thumb.append(vehicleImage(vehicle));
    thumb.title = vehicle.name || String(vehicle.address || "");
  } else {
    const placeholder = document.createElement("span");
    placeholder.textContent = "-";
    thumb.append(placeholder);
    thumb.removeAttribute("title");
  }
}

function collectConsistMembers(memberEditor) {
  return Array.from(memberEditor.querySelectorAll(".vehicle-consist-member-row"))
    .map((row, index) => {
      const vehicleId = row.querySelector(".vehicle-consist-member-select")?.value || "";
      const reverse = row.querySelector(".vehicle-consist-reverse-button")?.getAttribute("aria-pressed") === "true";
      return vehicleId ? {
        vehicle_id: vehicleId,
        direction: reverse ? "reverse" : "forward",
        order: index + 1
      } : null;
    })
    .filter(Boolean);
}

function findConsistForVehicle(vehicleId, consists) {
  return (consists || []).find((consist) => String(consist.control_vehicle_id || "") === String(vehicleId || "")) || null;
}

function functionsForVehicle(functionsByVehicle, vehicleId) {
  if (functionsByVehicle instanceof Map) {
    return functionsByVehicle.get(vehicleId) || functionsByVehicle.get(String(vehicleId)) || [];
  }
  return functionsByVehicle?.[vehicleId] || functionsByVehicle?.[String(vehicleId)] || [];
}

function renderVehicleImageUploader(vehicle, handlers) {
  const preview = document.createElement("div");
  preview.className = "image-preview vehicle-image-upload";
  const fileInput = document.createElement("input");
  fileInput.type = "file";
  fileInput.accept = "image/png,image/jpeg,image/webp";
  fileInput.hidden = true;
  const button = document.createElement("button");
  button.type = "button";
  button.className = "vehicle-image-upload-button";
  if (vehicle?.image_path) {
    button.append(vehicleImage(vehicle));
  } else {
    const add = document.createElement("span");
    add.className = "vehicle-image-add";
    add.textContent = "+";
    const text = document.createElement("span");
    text.textContent = "添加图片";
    button.append(add, text);
  }
  button.addEventListener("click", () => fileInput.click());
  fileInput.addEventListener("change", () => {
    const file = fileInput.files?.[0];
    if (file) {
      handlers.onImageFile?.(file);
    }
    fileInput.value = "";
  });
  preview.append(button, fileInput);
  return preview;
}

export function renderLocoControl(container, vehicle, functions, control, handlers = {}) {
  container.replaceChildren();
  if (!vehicle) {
    container.hidden = true;
    return;
  }
  container.hidden = false;
  const toolbar = subviewToolbar("车辆控制", handlers.onBack);
  const shell = document.createElement("div");
  shell.className = "loco-control";
  const imagePanel = document.createElement("div");
  imagePanel.className = "image-preview large";
  imagePanel.append(vehicleImage(vehicle));

  const speedPanel = document.createElement("section");
  speedPanel.className = "speed-panel";
  const name = document.createElement("h2");
  name.textContent = `${vehicle.name} / ${vehicle.address}`;
  const gauge = document.createElement("meter");
  gauge.className = "speed-gauge";
  gauge.min = "0";
  gauge.max = "126";
  gauge.value = String(control.speed || 0);
  const speedText = document.createElement("strong");
  speedText.textContent = `${control.speed || 0}`;
  const slider = document.createElement("input");
  slider.type = "range";
  slider.min = "0";
  slider.max = "126";
  slider.value = String(control.speed || 0);
  slider.addEventListener("input", () => handlers.onSpeed?.(Number(slider.value), control.direction || "forward"));
  const directionRow = document.createElement("div");
  directionRow.className = "segmented";
  const reverse = segmentButton("←", control.direction === "reverse", () => handlers.onDirection?.("reverse"));
  reverse.title = "后退";
  reverse.setAttribute("aria-label", "后退");
  const forward = segmentButton("→", control.direction !== "reverse", () => handlers.onDirection?.("forward"));
  forward.title = "前进";
  forward.setAttribute("aria-label", "前进");
  directionRow.append(reverse, forward);
  const stop = document.createElement("button");
  stop.type = "button";
  stop.className = "danger";
  stop.textContent = "紧急停车";
  stop.addEventListener("click", () => handlers.onEmergencyStop?.());
  speedPanel.append(name, gauge, speedText, slider, directionRow, stop);

  const functionPanel = document.createElement("section");
  functionPanel.className = "function-grid";
  const functionIconCatalog = handlers.functionIconCatalog || DEFAULT_FUNCTION_ICON_CATALOG;
  for (const fn of functions) {
    const button = document.createElement("button");
    button.type = "button";
    const icon = resolveFunctionIcon(fn, functionIconCatalog);
    appendFunctionButtonContent(button, fn, icon);
    button.addEventListener("click", () => handlers.onFunction?.(fn.function_number, true));
    functionPanel.append(button);
  }
  if (!functions.length) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "暂无功能键";
    functionPanel.append(empty);
  }
  shell.append(imagePanel, speedPanel, functionPanel);
  container.append(toolbar, shell);
}

