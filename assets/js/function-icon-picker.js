const FUNCTION_ICON_PICKER_GROUPS = [
  {
    key: "lights",
    label: "灯光控制",
    patterns: ["light", "lamp", "灯", "前灯", "尾灯", "头灯", "室内灯", "车厢灯", "驾驶室灯", "信号灯", "标志灯", "车号灯", "方向牌灯", "踏脚灯"]
  },
  {
    key: "engine",
    label: "引擎类",
    patterns: ["engine", "rpm", "diesel", "compressor", "fan", "generator", "preheat", "hood", "发动机", "内燃机", "柴油机", "转速", "空压机", "风扇", "发电机", "预热", "引擎盖"]
  },
  {
    key: "crane",
    label: "起重机控制",
    patterns: ["crane", "load-lift", "load_lift", "turntable", "吊车", "吊臂", "吊钩", "支腿", "升降货", "转车台", "自由拖行"]
  },
  {
    key: "running-sound",
    label: "运行音效",
    patterns: ["rail-sound", "curve-sound", "rail_kick", "curve_sound", "sound_brake", "轮轨声", "道岔", "弯道", "曲线声", "摩擦声"]
  },
  {
    key: "steam",
    label: "蒸汽机类",
    patterns: ["steam", "coal", "drain", "injector", "water-pump", "firebox", "蒸汽", "发烟", "加煤", "铲煤", "泄压", "排水", "注水", "注油", "抽水泵", "给水泵", "火箱"]
  },
  {
    key: "voice",
    label: "音效",
    patterns: ["horn", "whistle", "bell", "announcement", "radio", "music", "bugle", "door", "window", "鸣笛", "汽笛", "电笛", "风笛", "铃声", "广播", "手台", "对讲机", "音乐", "发车音乐", "车门", "开门", "关门", "车窗", "开窗", "关窗"]
  },
  {
    key: "control",
    label: "控制功能类",
    patterns: ["function", "volume", "mute", "brake", "pantograph", "coupler", "load-mode", "weight", "gear", "gear switch", "hump_gear", "sander", "warning", "shunting", "signal", "generic", "功能", "音量", "静音", "刹车", "停车", "制动", "缓解", "升弓", "降弓", "连挂", "解挂", "重载", "重车模式", "调车", "撒沙", "告警"]
  },
  {
    key: "other",
    label: "其他",
    patterns: []
  }
];

export function renderFunctionIconPicker(functionIconCatalog, selectedIconName, onSelect) {
  const dialog = document.createElement("dialog");
  dialog.className = "function-icon-picker-dialog";
  const header = document.createElement("div");
  header.className = "function-icon-picker-header";
  const title = document.createElement("h2");
  title.textContent = "选择功能图标";
  const close = document.createElement("button");
  close.type = "button";
  close.className = "function-icon-picker-close";
  close.setAttribute("aria-label", "关闭");
  close.textContent = "×";
  close.addEventListener("click", () => dialog.close());
  header.append(title, close);
  const groups = document.createElement("div");
  groups.className = "icon-picker-groups";
  for (const group of resolveFunctionIconPickerGroups(functionIconCatalog)) {
    const section = document.createElement("section");
    section.className = "icon-picker-group";
    section.dataset.groupKey = group.key;
    const heading = document.createElement("h3");
    heading.className = "icon-picker-group-title";
    heading.textContent = group.label;
    const grid = document.createElement("div");
    grid.className = "icon-picker-grid";
    for (const icon of group.icons) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "icon-picker-option";
      button.classList.toggle("active", icon.key === selectedIconName);
      const image = document.createElement("img");
      image.className = "function-icon";
      image.src = icon.path.startsWith("/") ? icon.path : `/${icon.path}`;
      image.alt = "";
      image.loading = "lazy";
      const label = document.createElement("span");
      label.textContent = icon.label || icon.key;
      button.append(image, label);
      button.addEventListener("click", () => {
        onSelect?.(icon.key);
        dialog.close();
      });
      grid.append(button);
    }
    section.append(heading, grid);
    groups.append(section);
  }
  dialog.append(header, groups);
  dialog.addEventListener("close", () => {
    document.documentElement.classList.remove("function-icon-picker-open");
    document.body.classList.remove("function-icon-picker-open");
    dialog.remove();
  });
  document.body.append(dialog);
  document.documentElement.classList.add("function-icon-picker-open");
  document.body.classList.add("function-icon-picker-open");
  if (typeof dialog.showModal === "function") {
    dialog.showModal();
  } else {
    dialog.setAttribute("open", "");
  }
}

function resolveFunctionIconPickerGroups(functionIconCatalog) {
  const grouped = new Map(FUNCTION_ICON_PICKER_GROUPS.map((group) => [group.key, {...group, icons: []}]));
  for (const icon of resolveIconCatalogEntries(functionIconCatalog)) {
    const group = resolveFunctionIconPickerGroup(icon);
    grouped.get(group.key)?.icons.push(icon);
  }
  return FUNCTION_ICON_PICKER_GROUPS
    .map((group) => grouped.get(group.key))
    .filter((group) => group?.icons.length);
}

function resolveFunctionIconPickerGroup(icon) {
  const haystack = [icon.key, icon.label, ...(icon.keywords || [])].join(" ").toLowerCase();
  return FUNCTION_ICON_PICKER_GROUPS.find((group) => group.patterns.some((pattern) => haystack.includes(pattern.toLowerCase())))
    || FUNCTION_ICON_PICKER_GROUPS[FUNCTION_ICON_PICKER_GROUPS.length - 1];
}

function resolveIconCatalogEntries(functionIconCatalog) {
  return Object.entries(functionIconCatalog.icons || {})
    .map(([key, icon]) => ({key, ...icon}))
    .sort((left, right) => (left.label || left.key).localeCompare(right.label || right.key, "zh-Hans-CN"));
}
