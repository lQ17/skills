const fs = require('fs');

const inputPath = process.argv[2] || 'sb3_extracted/project.json';
const outputPath = process.argv[3] || null;

const project = JSON.parse(fs.readFileSync(inputPath, 'utf8'));
const targets = project.targets || [];

// Translate English key/option names to Chinese
const KEY_CN = {
  'space': '空格', 'up arrow': '上箭头', 'down arrow': '下箭头',
  'left arrow': '左箭头', 'right arrow': '右箭头',
  'any': '任意键', 'a': 'A', 'b': 'B', 'c': 'C', 'd': 'D', 'e': 'E',
};

const PROP_CN = {
  'x position': 'x坐标', 'y position': 'y坐标', 'direction': '方向',
  'costume #': '造型编号', 'costume name': '造型名称',
  'size': '大小', 'volume': '音量',
  'backdrop #': '背景编号', 'backdrop name': '背景名称',
};

const OPCODE_CN = {
  event_whenflagclicked: '当 绿旗 被点击',
  event_whenbroadcastreceived: '当接收到广播',
  event_whenthisspriteclicked: '当这个角色被点击',
  event_whenkeypressed: '当按下键',
  event_whenbackdropswitchesto: '当背景换成',
  event_whengreaterthan: '当',
  event_broadcast: '广播',
  event_broadcastandwait: '广播并等待',
  motion_movesteps: '移动',
  motion_turnright: '右转',
  motion_turnleft: '左转',
  motion_pointindirection: '面向方向',
  motion_gotoxy: '移到xy',
  motion_goto: '移到',
  motion_glidesecstoxy: '滑行到xy',
  motion_changexby: 'x坐标增加',
  motion_setx: 'x坐标设为',
  motion_changeyby: 'y坐标增加',
  motion_sety: 'y坐标设为',
  motion_ifonedgebounce: '碰到边缘就反弹',
  motion_setrotationstyle: '旋转方式设为',
  looks_sayforsecs: '说…秒',
  looks_say: '说',
  looks_thinkforsecs: '思考…秒',
  looks_think: '思考',
  looks_show: '显示',
  looks_hide: '隐藏',
  looks_changeeffectby: '特效增加',
  looks_seteffectto: '特效设为',
  looks_cleargraphiceffects: '清除图形特效',
  looks_changesizeby: '大小增加',
  looks_setsizeto: '大小设为',
  looks_switchcostumeto: '换成造型',
  looks_nextcostume: '下一个造型',
  looks_switchbackdropto: '换成背景',
  looks_nextbackdrop: '下一个背景',
  sound_play: '播放声音',
  sound_playuntildone: '播放声音直到播完',
  sound_stopallsounds: '停止所有声音',
  sound_setvolumeto: '音量设为',
  sound_changevolumeby: '音量增加',
  control_forever: '重复执行',
  control_repeat: '重复执行',
  control_if: '如果…那么',
  control_if_else: '如果…那么…否则',
  control_stop: '停止',
  control_wait: '等待',
  control_wait_until: '等待直到',
  control_repeat_until: '重复执行直到',
  control_start_as_clone: '当作为克隆体启动时',
  control_create_clone_of: '克隆',
  control_delete_this_clone: '删除此克隆体',
  sensing_touchingobject: '碰到',
  sensing_touchingcolor: '碰到颜色',
  sensing_distanceto: '到…的距离',
  sensing_askandwait: '询问并等待',
  sensing_answer: '回答',
  sensing_keypressed: '按下键',
  sensing_mousedown: '按下鼠标',
  sensing_mousex: '鼠标x坐标',
  sensing_mousey: '鼠标y坐标',
  sensing_setdragmode: '拖动模式',
  sensing_loudness: '响度',
  sensing_timer: '计时器',
  sensing_resettimer: '计时器归零',
  sensing_of: '…的…',
  sensing_current: '当前时间',
  sensing_username: '用户名',
  data_setvariableto: '将变量设为',
  data_changevariableby: '将变量增加',
  data_showvariable: '显示变量',
  data_hidevariable: '隐藏变量',
  operator_add: '+',
  operator_subtract: '-',
  operator_multiply: '*',
  operator_divide: '/',
  operator_random: '随机数',
  operator_gt: '>',
  operator_lt: '<',
  operator_equals: '=',
  operator_and: '且',
  operator_or: '或',
  operator_not: '不成立',
  operator_join: '连接',
  operator_letter_of: '第…个字符',
  operator_length: '长度',
  operator_contains: '包含',
  operator_mod: '%',
  operator_round: '四舍五入',
  operator_mathop: '数学函数',
  procedures_definition: '定义',
  procedures_call: '调用函数',
  pen_clear: '清除所有画笔',
  pen_stamp: '图章',
  pen_pendown: '落笔',
  pen_penup: '抬笔',
  pen_setpencolortocolor: '画笔颜色设为',
  pen_setpensizeto: '画笔大小设为',
  pen_changepensizeby: '画笔大小增加',
};

// Resolve an input (which can be literal array or block reference) to readable text
function resolveInput(blocks, input, _visited) {
  if (!input) return '?';
  const val = input[1];
  if (val === undefined || val === null) return '?';
  if (Array.isArray(val)) {
    // literal [type, value]
    return String(val[1]);
  }
  // Block reference
  return resolveReporter(blocks, val, _visited);
}

// Resolve a reporter block to readable text
// _visited: Set of block IDs already visited (cycle detection)
function resolveReporter(blocks, blockId, _visited) {
  if (!blockId) return '?';
  const b = blocks[blockId];
  if (!b) return '?';

  // Cycle detection
  if (!_visited) _visited = new Set();
  if (_visited.has(blockId)) return '(循环引用)';
  _visited.add(blockId);

  const op = b.opcode;
  if (!op) return '?';
  const inputs = b.inputs || {};
  const fields = b.fields || {};

  // Helper to pass visited set through
  const ri = (inp) => resolveInput(blocks, inp, _visited);

  if (op === 'data_variable') return `[${fields.VARIABLE ? fields.VARIABLE[0] : '变量'}]`;
  if (op === 'data_listcontents') return `[列表${fields.LIST ? fields.LIST[0] : ''}]`;
  if (op === 'sensing_answer') return '(回答)';
  if (op === 'sensing_timer') return '(计时器)';
  if (op === 'sensing_loudness') return '(响度)';
  if (op === 'sensing_mousex') return '(鼠标x)';
  if (op === 'sensing_mousey') return '(鼠标y)';
  if (op === 'motion_xposition') return '(x坐标)';
  if (op === 'motion_yposition') return '(y坐标)';
  if (op === 'motion_direction') return '(方向)';
  if (op === 'looks_size') return '(大小)';
  if (op === 'sound_volume') return '(音量)';
  if (op === 'sensing_dayssince2000') return '(2000年至今天数)';
  if (op === 'sensing_username') return '(用户名)';
  if (op === 'looks_costumenumbername') {
    const numName = fields.NUMBER_NAME ? fields.NUMBER_NAME[0] : '编号';
    return `(造型${numName})`;
  }
  if (op === 'looks_backdropnumbername') {
    const numName = fields.NUMBER_NAME ? fields.NUMBER_NAME[0] : '编号';
    return `(背景${numName})`;
  }

  // List reporters
  if (op === 'data_itemoflist') return `[${fields.LIST ? fields.LIST[0] : '列表'}]的第${ri(inputs.INDEX)}项`;
  if (op === 'data_itemnumoflist') return `${ri(inputs.ITEM)}在[${fields.LIST ? fields.LIST[0] : '列表'}]中的位置`;
  if (op === 'data_lengthoflist') return `[${fields.LIST ? fields.LIST[0] : '列表'}]的长度`;
  if (op === 'data_listcontainsitem') return `[${fields.LIST ? fields.LIST[0] : '列表'}]包含${ri(inputs.ITEM)}`;

  // Argument reporters (custom block parameters)
  if (op === 'argument_reporter_string_number') return `{${fields.VALUE ? fields.VALUE[0] : '参数'}}`;
  if (op === 'argument_reporter_boolean') return `{${fields.VALUE ? fields.VALUE[0] : '参数'}}`;

  if (op === 'sensing_keypressed') {
    const key = ri(inputs.KEY_OPTION);
    return `按下[${KEY_CN[key] || key}]键`;
  }
  if (op === 'sensing_touchingobject') return `碰到(${ri(inputs.TOUCHINGOBJECTMENU)})`;
  if (op === 'sensing_mousedown') return '按下鼠标';
  if (op === 'sensing_coloristouchingcolor') return `颜色${ri(inputs.COLOR)}碰到颜色${ri(inputs.COLOR2)}`;

  if (op === 'sensing_distanceto') return `到(${ri(inputs.DISTANCETOMENU)})的距离`;
  if (op === 'sensing_current') {
    const current = fields.CURRENTMENU ? fields.CURRENTMENU[0] : '时间';
    return `(当前${current})`;
  }

  if (op === 'operator_add') return `(${ri(inputs.NUM1)} + ${ri(inputs.NUM2)})`;
  if (op === 'operator_subtract') return `(${ri(inputs.NUM1)} - ${ri(inputs.NUM2)})`;
  if (op === 'operator_multiply') return `(${ri(inputs.NUM1)} * ${ri(inputs.NUM2)})`;
  if (op === 'operator_divide') return `(${ri(inputs.NUM1)} / ${ri(inputs.NUM2)})`;
  if (op === 'operator_mod') return `(${ri(inputs.NUM1)} % ${ri(inputs.NUM2)})`;
  if (op === 'operator_gt') return `(${ri(inputs.OPERAND1)} > ${ri(inputs.OPERAND2)})`;
  if (op === 'operator_lt') return `(${ri(inputs.OPERAND1)} < ${ri(inputs.OPERAND2)})`;
  if (op === 'operator_equals') return `(${ri(inputs.OPERAND1)} = ${ri(inputs.OPERAND2)})`;
  if (op === 'operator_and') return `(${ri(inputs.OPERAND1)} 且 ${ri(inputs.OPERAND2)})`;
  if (op === 'operator_or') return `(${ri(inputs.OPERAND1)} 或 ${ri(inputs.OPERAND2)})`;
  if (op === 'operator_not') return `(不成立 ${ri(inputs.OPERAND)})`;
  if (op === 'operator_join') return `连接(${ri(inputs.STRING1)}, ${ri(inputs.STRING2)})`;
  if (op === 'operator_letter_of') return `(${ri(inputs.STRING)} 的第 ${ri(inputs.LETTER)} 个字符)`;
  if (op === 'operator_length') return `(${ri(inputs.STRING)} 的长度)`;
  if (op === 'operator_contains') return `(${ri(inputs.STRING1)} 包含 ${ri(inputs.STRING2)})`;
  if (op === 'operator_random') return `随机(${ri(inputs.FROM)}~${ri(inputs.TO)})`;
  if (op === 'operator_round') return `四舍五入(${ri(inputs.NUM)})`;
  if (op === 'operator_mathop') {
    const func = fields.OPERATOR ? fields.OPERATOR[0] : '?';
    return `${func}(${ri(inputs.NUM)})`;
  }
  if (op === 'sensing_of') {
    const prop = fields.PROPERTY ? fields.PROPERTY[0] : '?';
    return `(${ri(inputs.OBJECT)} 的 ${PROP_CN[prop] || prop})`;
  }

  // Menu blocks (dropdowns / shadow blocks) - just return the field value
  if (op.endsWith('_menu') || op.endsWith('_options') || op.endsWith('menu') ||
      op === 'looks_costume' || op === 'looks_backdrops' ||
      op === 'sound_sounds_menu' || op === 'event_broadcast_menu' ||
      op === 'sensing_touchingobjectmenu' || op === 'sensing_distancetomenu' ||
      op === 'sensing_keyoptions' ||
      op === 'control_create_clone_of_menu' || op === 'sensing_of_object_menu' ||
      op === 'motion_pointtowards_menu' || op === 'motion_goto_menu' ||
      op === 'motion_glideto_menu') {
    // Menu blocks store the selection in their fields
    for (const [, val] of Object.entries(fields)) {
      if (val && val[0]) {
        const v = val[0];
        // Translate key names if this is a key options menu
        if (op === 'sensing_keyoptions') return KEY_CN[v] || v;
        return v;
      }
    }
    return '?';
  }

  // Fallback: label + fields
  let parts = [OPCODE_CN[op] || op];
  for (const [, val] of Object.entries(fields)) {
    if (val && val[0]) parts.push(val[0]);
  }
  return parts.join(' ');
}

// Format a single block into a readable line
function formatBlock(blocks, blockId) {
  const b = blocks[blockId];
  if (!b) return '?';
  const op = b.opcode;
  if (!op) return '?';
  const inputs = b.inputs || {};
  const fields = b.fields || {};
  const ri = (inp) => resolveInput(blocks, inp, new Set([blockId]));

  if (op === 'event_whenflagclicked') return '当 绿旗 被点击';
  if (op === 'event_whenbroadcastreceived') return `当接收到广播 [${fields.BROADCAST_OPTION ? fields.BROADCAST_OPTION[0] : '?'}]`;
  if (op === 'event_whenthisspriteclicked') return '当这个角色被点击';
  if (op === 'event_whenstageclicked') return '当舞台被点击';
  if (op === 'event_whenkeypressed') {
    const key = fields.KEY_OPTION ? fields.KEY_OPTION[0] : '?';
    return `当按下 [${KEY_CN[key] || key}] 键`;
  }
  if (op === 'event_whenbackdropswitchesto') return `当背景换成 [${fields.BACKDROP ? fields.BACKDROP[0] : '?'}]`;
  if (op === 'event_whengreaterthan') {
    const menu = fields.WHENGREATERTHANMENU ? fields.WHENGREATERTHANMENU[0] : '?';
    return `当 ${menu} > ${ri(inputs.VALUE)}`;
  }
  if (op === 'event_broadcast') return `广播 [${ri(inputs.BROADCAST_INPUT)}]`;
  if (op === 'event_broadcastandwait') return `广播并等待 [${ri(inputs.BROADCAST_INPUT)}]`;

  if (op === 'motion_gotoxy') return `移到 x:${ri(inputs.X)} y:${ri(inputs.Y)}`;
  if (op === 'motion_glidesecstoxy') return `滑行 ${ri(inputs.SECS)} 秒到 x:${ri(inputs.X)} y:${ri(inputs.Y)}`;
  if (op === 'motion_movesteps') return `移动 ${ri(inputs.STEPS)} 步`;
  if (op === 'motion_turnright') return `右转 ${ri(inputs.DEGREES)} 度`;
  if (op === 'motion_turnleft') return `左转 ${ri(inputs.DEGREES)} 度`;
  if (op === 'motion_setx') return `将x坐标设为 ${ri(inputs.X)}`;
  if (op === 'motion_sety') return `将y坐标设为 ${ri(inputs.Y)}`;
  if (op === 'motion_changexby') return `将x坐标增加 ${ri(inputs.DX)}`;
  if (op === 'motion_changeyby') return `将y坐标增加 ${ri(inputs.DY)}`;
  if (op === 'motion_pointindirection') return `面向 ${ri(inputs.DIRECTION)} 方向`;
  if (op === 'motion_setrotationstyle') {
    const styleMap = {'left-right': '左右翻转', "don't rotate": '不旋转', 'all around': '任意'};
    const style = fields.STYLE ? fields.STYLE[0] : '?';
    return `旋转方式设为 [${styleMap[style] || style}]`;
  }
  if (op === 'motion_ifonedgebounce') return '碰到边缘就反弹';
  if (op === 'motion_goto') return `移到 ${ri(inputs.TO)}`;

  if (op === 'looks_show') return '显示';
  if (op === 'looks_hide') return '隐藏';
  if (op === 'looks_switchcostumeto') return `换成造型 ${ri(inputs.COSTUME)}`;
  if (op === 'looks_nextcostume') return '下一个造型';
  if (op === 'looks_switchbackdropto') return `换成背景 ${ri(inputs.BACKDROP)}`;
  if (op === 'looks_switchbackdroptoandwait') return `换成背景 ${ri(inputs.BACKDROP)} 并等待`;
  if (op === 'looks_nextbackdrop') return '下一个背景';
  if (op === 'looks_sayforsecs') return `说 ${ri(inputs.MESSAGE)} ${ri(inputs.SECS)} 秒`;
  if (op === 'looks_say') return `说 ${ri(inputs.MESSAGE)}`;
  if (op === 'looks_thinkforsecs') return `思考 ${ri(inputs.MESSAGE)} ${ri(inputs.SECS)} 秒`;
  if (op === 'looks_think') return `思考 ${ri(inputs.MESSAGE)}`;
  if (op === 'looks_changesizeby') return `大小增加 ${ri(inputs.CHANGE)}`;
  if (op === 'looks_setsizeto') return `大小设为 ${ri(inputs.SIZE)}`;
  if (op === 'looks_changeeffectby') return `${fields.EFFECT ? fields.EFFECT[0] : '特效'} 增加 ${ri(inputs.CHANGE)}`;
  if (op === 'looks_seteffectto') return `${fields.EFFECT ? fields.EFFECT[0] : '特效'} 设为 ${ri(inputs.VALUE)}`;
  if (op === 'looks_cleargraphiceffects') return '清除图形特效';
  if (op === 'looks_gotofrontback') return `移到最${fields.FRONT_BACK ? fields.FRONT_BACK[0] : '?'}层`;
  if (op === 'looks_goforwardbackwardlayers') return `${fields.FORWARD_BACKWARD ? fields.FORWARD_BACKWARD[0] : '前移'} ${ri(inputs.NUM)} 层`;

  if (op === 'sound_play') return `播放声音 ${ri(inputs.SOUND_MENU)}`;
  if (op === 'sound_playuntildone') return `播放声音 ${ri(inputs.SOUND_MENU)} 直到播完`;
  if (op === 'sound_stopallsounds') return '停止所有声音';
  if (op === 'sound_seteffectto') return `音效 ${fields.EFFECT ? fields.EFFECT[0] : ''} 设为 ${ri(inputs.VALUE)}`;
  if (op === 'sound_changeeffectby') return `音效 ${fields.EFFECT ? fields.EFFECT[0] : ''} 增加 ${ri(inputs.VALUE)}`;
  if (op === 'sound_cleareffects') return '清除音效';
  if (op === 'sound_setvolumeto') return `音量设为 ${ri(inputs.VOLUME)}`;
  if (op === 'sound_changevolumeby') return `音量增加 ${ri(inputs.VOLUME)}`;

  if (op === 'control_wait') return `等待 ${ri(inputs.DURATION)} 秒`;
  if (op === 'control_wait_until') return `等待直到 ${ri(inputs.CONDITION)}`;
  if (op === 'control_stop') return `停止 [${fields.STOP_OPTION ? fields.STOP_OPTION[0] : '全部'}]`;
  if (op === 'control_create_clone_of') return `克隆 ${ri(inputs.CLONE_OPTION)}`;
  if (op === 'control_start_as_clone') return '当作为克隆体启动时';
  if (op === 'control_delete_this_clone') return '删除此克隆体';

  if (op === 'data_setvariableto') return `将 [${fields.VARIABLE ? fields.VARIABLE[0] : '?'}] 设为 ${ri(inputs.VALUE)}`;
  if (op === 'data_changevariableby') return `将 [${fields.VARIABLE ? fields.VARIABLE[0] : '?'}] 增加 ${ri(inputs.VALUE)}`;
  if (op === 'data_showvariable') return `显示变量 [${fields.VARIABLE ? fields.VARIABLE[0] : '?'}]`;
  if (op === 'data_hidevariable') return `隐藏变量 [${fields.VARIABLE ? fields.VARIABLE[0] : '?'}]`;

  // List operations
  if (op === 'data_addtolist') return `将 ${ri(inputs.ITEM)} 加入 [${fields.LIST ? fields.LIST[0] : '列表'}]`;
  if (op === 'data_deleteoflist') return `删除 [${fields.LIST ? fields.LIST[0] : '列表'}] 的第 ${ri(inputs.INDEX)} 项`;
  if (op === 'data_deletealloflist') return `删除 [${fields.LIST ? fields.LIST[0] : '列表'}] 的全部项目`;
  if (op === 'data_insertatlist') return `在 [${fields.LIST ? fields.LIST[0] : '列表'}] 的第 ${ri(inputs.INDEX)} 项前插入 ${ri(inputs.ITEM)}`;
  if (op === 'data_replaceitemoflist') return `将 [${fields.LIST ? fields.LIST[0] : '列表'}] 的第 ${ri(inputs.INDEX)} 项替换为 ${ri(inputs.ITEM)}`;
  if (op === 'data_showlist') return `显示列表 [${fields.LIST ? fields.LIST[0] : '?'}]`;
  if (op === 'data_hidelist') return `隐藏列表 [${fields.LIST ? fields.LIST[0] : '?'}]`;

  if (op === 'sensing_touchingobject') return `碰到 ${ri(inputs.TOUCHINGOBJECTMENU)}`;
  if (op === 'sensing_touchingcolor') return `碰到颜色 ${ri(inputs.COLOR)}`;
  if (op === 'sensing_coloristouchingcolor') return `颜色 ${ri(inputs.COLOR)} 碰到颜色 ${ri(inputs.COLOR2)}`;
  if (op === 'sensing_distanceto') return `到 ${ri(inputs.DISTANCETOMENU)} 的距离`;
  if (op === 'sensing_askandwait') return `询问 ${ri(inputs.QUESTION)} 并等待`;
  if (op === 'sensing_setdragmode') return `拖动模式设为 [${fields.DRAG_MODE ? fields.DRAG_MODE[0] : '?'}]`;
  if (op === 'sensing_resettimer') return '计时器归零';

  if (op === 'pen_clear') return '清除所有画笔';
  if (op === 'pen_stamp') return '图章';
  if (op === 'pen_pendown') return '落笔';
  if (op === 'pen_penup') return '抬笔';
  if (op === 'pen_setpencolortocolor') return `画笔颜色设为 ${ri(inputs.COLOR)}`;
  if (op === 'pen_setpensizeto') return `画笔大小设为 ${ri(inputs.SIZE)}`;
  if (op === 'pen_changepensizeby') return `画笔大小增加 ${ri(inputs.SIZE)}`;

  if (op === 'procedures_definition') return '定义自定义函数';
  if (op === 'procedures_call') {
    const proc = b.mutation && b.mutation.proccode ? b.mutation.proccode : '自定义函数';
    return `调用 ${proc}`;
  }

  // Fallback
  let parts = [OPCODE_CN[op] || op];
  for (const [, val] of Object.entries(fields)) {
    if (val && val[0]) parts.push(`[${val[0]}]`);
  }
  for (const [, inp] of Object.entries(inputs)) {
    parts.push(ri(inp));
  }
  return parts.join(' ');
}

// Recursively render a chain of blocks, descending into substacks
function renderChain(blocks, startId, depth, output, _chainVisited) {
  let current = startId;
  let safety = 0;
  if (!_chainVisited) _chainVisited = new Set();
  while (current && safety < 500) {
    safety++;
    // Cycle detection in chain
    if (_chainVisited.has(current)) {
      output.push('  '.repeat(depth) + '(循环引用，已跳过)');
      break;
    }
    _chainVisited.add(current);

    const b = blocks[current];
    if (!b) break;

    const op = b.opcode;
    if (!op) { current = b.next; continue; }

    const inputs = b.inputs || {};
    const indent = '  '.repeat(depth);
    const ri = (inp) => resolveInput(blocks, inp, new Set(_chainVisited));

    // Depth limit
    if (depth > 30) {
      output.push(`${indent}... (嵌套过深，已截断)`);
      break;
    }

    // C-blocks (have substack)
    if (op === 'control_forever') {
      output.push(`${indent}重复执行:`);
      if (inputs.SUBSTACK && inputs.SUBSTACK[1]) {
        renderChain(blocks, inputs.SUBSTACK[1], depth + 1, output, new Set(_chainVisited));
      }
      output.push(`${indent}结束 重复执行`);
    } else if (op === 'control_repeat') {
      const times = ri(inputs.TIMES);
      output.push(`${indent}重复执行 ${times} 次:`);
      if (inputs.SUBSTACK && inputs.SUBSTACK[1]) {
        renderChain(blocks, inputs.SUBSTACK[1], depth + 1, output, new Set(_chainVisited));
      }
      output.push(`${indent}结束 重复`);
    } else if (op === 'control_if') {
      const cond = ri(inputs.CONDITION);
      output.push(`${indent}如果 ${cond} 那么:`);
      if (inputs.SUBSTACK && inputs.SUBSTACK[1]) {
        renderChain(blocks, inputs.SUBSTACK[1], depth + 1, output, new Set(_chainVisited));
      }
      output.push(`${indent}结束 如果`);
    } else if (op === 'control_if_else') {
      const cond = ri(inputs.CONDITION);
      output.push(`${indent}如果 ${cond} 那么:`);
      if (inputs.SUBSTACK && inputs.SUBSTACK[1]) {
        renderChain(blocks, inputs.SUBSTACK[1], depth + 1, output, new Set(_chainVisited));
      }
      output.push(`${indent}否则:`);
      if (inputs.SUBSTACK2 && inputs.SUBSTACK2[1]) {
        renderChain(blocks, inputs.SUBSTACK2[1], depth + 1, output, new Set(_chainVisited));
      }
      output.push(`${indent}结束 如果-否则`);
    } else if (op === 'control_repeat_until') {
      const cond = ri(inputs.CONDITION);
      output.push(`${indent}重复执行直到 ${cond}:`);
      if (inputs.SUBSTACK && inputs.SUBSTACK[1]) {
        renderChain(blocks, inputs.SUBSTACK[1], depth + 1, output, new Set(_chainVisited));
      }
      output.push(`${indent}结束 重复直到`);
    } else {
      // Regular stack block
      output.push(`${indent}${formatBlock(blocks, current)}`);
    }

    current = b.next;
  }
  if (safety >= 500) {
    output.push('  '.repeat(depth) + '... (脚本过长，已截断)');
  }
}

// Parse all blocks for a target into scripts
function parseTarget(blocks) {
  const topBlocks = Object.keys(blocks).filter(id => {
    const b = blocks[id];
    return b.topLevel && b.opcode;
  });

  const scripts = [];
  for (const topId of topBlocks) {
    const output = [];
    renderChain(blocks, topId, 0, output);
    scripts.push(output);
  }
  return scripts;
}

// Build full output
const lines = [];

for (const target of targets) {
  lines.push('═'.repeat(60));
  lines.push(`角色: ${target.name || '(未命名)'}${target.isStage ? ' (舞台)' : ''}`);

  if (target.variables && Object.keys(target.variables).length > 0) {
    const vars = Object.entries(target.variables).map(([id, v]) => `${v[0]}=${v[1]}`);
    lines.push(`  变量: ${vars.join(', ')}`);
  }
  if (target.lists && Object.keys(target.lists).length > 0) {
    const lists = Object.entries(target.lists).map(([id, l]) => `${l[0]}=[${l[1].join(', ')}]`);
    lines.push(`  列表: ${lists.join(', ')}`);
  }
  if (Array.isArray(target.costumes) && target.costumes.length > 0) {
    const costumes = target.costumes.map(c => c.name || '?');
    lines.push(`  造型: ${costumes.join(', ')}`);
  }
  if (Array.isArray(target.sounds) && target.sounds.length > 0) {
    const sounds = target.sounds.map(s => s.name || '?');
    lines.push(`  声音: ${sounds.join(', ')}`);
  }
  lines.push('═'.repeat(60));

  if (!target.blocks || Object.keys(target.blocks).length === 0) {
    lines.push('  (无积木块)');
    lines.push('');
    continue;
  }

  const scripts = parseTarget(target.blocks);
  if (scripts.length === 0) {
    lines.push('  (无脚本)');
  }
  for (let i = 0; i < scripts.length; i++) {
    lines.push(`┌─ 脚本 ${i + 1} ─`);
    for (const line of scripts[i]) {
      lines.push(line);
    }
    lines.push(`└──────────`);
    lines.push('');
  }
}

const result = lines.join('\n');
console.log(result);
if (outputPath) {
  fs.writeFileSync(outputPath, result, 'utf8');
  console.log(`\n✅ 已保存到 ${outputPath}`);
}
