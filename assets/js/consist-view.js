export function renderConsistPanel(container, consists, vehicles, handlers = {}) {
  container.replaceChildren();
  const title = document.createElement("h2");
  title.textContent = "编组";
  const form = document.createElement("form");
  form.className = "stack-form";
  const nameLabel = document.createElement("label");
  nameLabel.textContent = "编组名称";
  const nameInput = document.createElement("input");
  nameInput.type = "text";
  nameInput.value = `编组 ${consists.length + 1}`;
  nameLabel.append(nameInput);
  const membersLabel = document.createElement("label");
  membersLabel.textContent = "成员车辆（最多8辆）";
  const select = document.createElement("select");
  select.multiple = true;
  select.size = Math.min(Math.max(vehicles.length, 3), 8);
  for (const vehicle of vehicles) {
    const option = document.createElement("option");
    option.value = vehicle.id;
    option.textContent = `${vehicle.name} / 地址 ${vehicle.address}`;
    select.append(option);
  }
  membersLabel.append(select);
  const createButton = document.createElement("button");
  createButton.type = "submit";
  createButton.textContent = "创建编组";
  form.append(nameLabel, membersLabel, createButton);
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const selectedIds = Array.from(select.selectedOptions).map((option) => option.value);
    const members = selectedIds.map((vehicleId, index) => {
      const vehicle = vehicles.find((item) => item.id === vehicleId);
      return {
        vehicle_id: vehicleId,
        address: vehicle?.address,
        direction: "forward",
        order: index + 1
      };
    });
    handlers.onCreate?.(nameInput.value.trim(), members);
  });

  const list = document.createElement("ul");
  list.replaceChildren(...consists.map((consist) => {
    const item = document.createElement("li");
    const name = document.createElement("input");
    name.type = "text";
    name.value = consist.name;
    const summary = document.createElement("span");
    summary.textContent = ` / ${consist.members.length} 辆`;
    const save = document.createElement("button");
    save.type = "button";
    save.textContent = "保存";
    save.addEventListener("click", () => handlers.onUpdate?.(consist.id, {name: name.value.trim()}));
    const speed = document.createElement("button");
    speed.type = "button";
    speed.textContent = "速度 20";
    speed.addEventListener("click", () => handlers.onSpeed?.(consist.id, 20, "forward"));
    const stop = document.createElement("button");
    stop.type = "button";
    stop.textContent = "停止";
    stop.addEventListener("click", () => handlers.onSpeed?.(consist.id, 0, "forward"));
    const remove = document.createElement("button");
    remove.type = "button";
    remove.textContent = "删除";
    remove.addEventListener("click", () => handlers.onDelete?.(consist.id));
    item.append(name, summary, save, speed, stop, remove);
    return item;
  }));
  container.append(title, form, list);
}
