import fs from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { FileBlob, PresentationFile } from 'file:///C:/Users/Aphelios/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs';

const root = 'F:/rob-memory/outputs/hunter_nav2_refined_20261028';
const build = `${root}/build`;
const source = 'C:/Users/Aphelios/Desktop/Hunter_Nav2_进展图解_20261027/Hunter_Nav2_Weekly_追加20261027截图.pptx';
const skill = 'C:/Users/Aphelios/.codex/plugins/cache/openai-primary-runtime/presentations/26.1025.11240/skills/presentations';
const finalPath = `${root}/delivery/Hunter_Nav2_组会进展_精简版_20261028.pptx`;
const python = 'C:/Users/Aphelios/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe';

const specs = [
  {
    title: '已有导航系统复用与关键配置',
    subtitle: '在个人工作区接入已有地图、底盘里程计与导航组件',
    footer: '2026.10.28 进展续页    复用师兄的地图和导航配置，实车跟踪仍待验证',
    'section-0': '系统接入',
    'body-0': '地图、雷达和底盘里程计已接入。\nAMCL 与规划器已激活。',
    'section-1': '规划与跟踪配置',
    'body-1': 'Smac Hybrid：最小转弯半径 1.6 m。\nRPP：期望速度 0.25 m/s。\n允许倒车，关闭原地朝向调整。',
    'section-2': '当前验证范围',
    'body-2': '路径跟踪与自主避障仍待验证。',
    'evidence-heading': '车体与障碍输入',
    'evidence-caption': '车体轮廓约 1.02 m × 0.79 m。\n代价地图使用二维扫描作为障碍输入。',
    notes: '2026 年 10 月 27 日和 28 日的用户回传：已有师兄参数、地图及行为树复用；底盘里程计 TF 可查询，AMCL 与规划器分别完成激活。1.6 m、0.25 m/s 和轮廓尺寸为运行配置值，并非实测转弯半径、速度或外形尺寸。',
  },
  {
    title: '初始定位与激光扫描观测',
    subtitle: '地图坐标、车体模型与二维激光扫描已在 RViz 中显示',
    footer: '2026.10.28 进展续页    位姿估计已更新，定位精度仍需进一步核验',
    'section-0': '初始定位',
    'body-0': 'AMCL 已激活并设置初始位姿。\nmap 到 base_link 的变换可查询。',
    'section-1': '静止更新',
    'body-1': '停车状态下请求定位更新。\n位置和朝向的不确定度有所下降。',
    'section-2': '仍需核验',
    'body-2': '部分激光点与地图墙线存在偏差。',
    'evidence-heading': '局部定位与扫描',
    'evidence-caption': '白色点为扫描结果，黑色线条为地图障碍。',
    image: 'C:/Users/Aphelios/AppData/Local/Temp/codex-clipboard-c33c1dc9-10c0-4c7c-ae9b-e4a8acc69aba.png',
    type: 'image/png',
    imageWidth: 620,
    imageHeight: 701,
    notes: '用户实际发送初始位姿后，map 到 base_link TF 可查询。三次静止更新前后，AMCL 估计的 X、Y、航向标准差约为 0.399 m、0.447 m、13.29°，变化为 0.299 m、0.345 m、11.03°。协方差标准差表示滤波估计不确定度，不能当作真实定位误差或定位通过。截图由用户提供。',
  },
  {
    title: '静态路径规划测试',
    subtitle: '使用已有地图和选定目标点，规划器返回一条短路径',
    footer: '2026.10.28 进展续页    本次仅计算路径，实车跟踪和避障尚未验证',
    'section-0': '测试方法',
    'body-0': '选择车前方的地图目标点。\n调用 ComputePathToPose 计算路径。',
    'section-1': '测试结果',
    'body-1': '规划动作返回 SUCCEEDED。\nRViz 显示绿色规划路径。',
    'section-2': '下一步',
    'body-2': '核验定位精度，再开展实车跟踪测试。',
    'evidence-heading': '短路径规划结果',
    'evidence-caption': '绿色线为规划路径，终端显示动作成功。',
    image: 'C:/Users/Aphelios/AppData/Local/Temp/codex-clipboard-e2caf988-efc3-449b-a545-aba9e8c4bdda.png',
    type: 'image/png',
    imageWidth: 1315,
    imageHeight: 654,
    notes: '用户在 map 坐标系中选取目标点 x=5.203141、y=-10.795444，使用 GridBased 规划器和当前位姿作为起点，调用 ComputePathToPose。用户截图显示 Goal finished with status: SUCCEEDED，RViz 显示绿色路径。此结果是静态路径计算成功，不代表车辆已沿路径行驶或避障。',
  },
];

function changeText(slide, name, value) {
  const matches = slide.shapes.items.filter(shape => shape.name === name);
  if (matches.length !== 1) throw new Error(`Expected one ${name}; found ${matches.length}`);
  matches[0].text = value;
}

async function replaceImage(slide, spec) {
  if (slide.images.items.length !== 1) throw new Error(`Expected one image, found ${slide.images.items.length}`);
  const bytes = await fs.readFile(spec.image);
  const im = slide.images.items[0];
  im.replace({ blob: bytes, contentType: spec.type, alt: spec['evidence-heading'], fit: 'contain' });
  const box = { left: 752, top: 306, width: 784, height: 423 };
  const scale = Math.min(box.width / spec.imageWidth, box.height / spec.imageHeight);
  const width = spec.imageWidth * scale, height = spec.imageHeight * scale;
  im.frame = { left: box.left + (box.width - width) / 2, top: box.top + (box.height - height) / 2, width, height };
  im.crop = { left: 0, right: 0, top: 0, bottom: 0 };
  im.fit = 'contain';
}

function addText(slide, name, text, position, isHeading = false) {
  const shape = slide.shapes.add({
    geometry: 'textbox', name, position, fill: 'none',
    line: { style: 'solid', fill: 'none', width: 0 },
  });
  shape.text = text;
  shape.text.style = { fontSize: isHeading ? 31 : 27, typeface: 'Microsoft YaHei', color: isHeading ? '#173E69' : '#24282F', bold: isHeading, alignment: 'left' };
  shape.text.insets = 0;
}

await fs.mkdir(build, { recursive: true });
const deck = await PresentationFile.importPptx(await FileBlob.load(source));
if (deck.slides.items.length !== 12) throw new Error(`Unexpected source count: ${deck.slides.items.length}`);
deck.slides.keep([0,1,2,3,4,5,6,7,8]);
for (let i = 0; i < specs.length; i++) {
  const slide = deck.slides.items[i + 6];
  const spec = specs[i];
  for (const key of ['title','subtitle','footer','section-0','body-0','section-1','body-1','section-2','body-2','evidence-heading','evidence-caption']) {
    changeText(slide, key, spec[key]);
  }
  if (i === 0) {
    const inspected = await deck.inspect({ kind: 'image', maxChars: 100000 });
    const images = inspected.ndjson.split('\n').filter(Boolean).map(line => JSON.parse(line));
    const target = images.find(record => record.kind === 'image' && record.slideIndex === 6);
    if (!target) throw new Error('Expected photo on slide 7');
    deck.delete(target.id);
    const caption = slide.shapes.items.find(shape => shape.name === 'evidence-caption');
    caption.position = { left: 752, top: 304, width: 784, height: 110 };
    caption.text.style = { fontSize: 27, typeface: 'Microsoft YaHei', color: '#24282F', alignment: 'left' };
    addText(slide, 'right-heading-1', '行为与速度接口', { left: 752, top: 448, width: 784, height: 44 }, true);
    addText(slide, 'right-body-1', '沿用不含 Spin 的导航行为树。\n导航速度使用独立测试话题。', { left: 752, top: 502, width: 784, height: 110 });
    addText(slide, 'right-heading-2', '当前进展', { left: 752, top: 680, width: 784, height: 44 }, true);
    addText(slide, 'right-body-2', '已完成一次静态路径规划。', { left: 752, top: 734, width: 784, height: 60 });
  } else {
    await replaceImage(slide, spec);
  }
  slide.speakerNotes.text = spec.notes;
}

for (let i = 0; i < deck.slides.items.length; i++) {
  const png = await deck.export({ slide: deck.slides.items[i], format: 'png', scale: 0.7 });
  await fs.writeFile(`${build}/draft-${String(i + 1).padStart(2,'0')}.png`, new Uint8Array(await png.arrayBuffer()));
}
const candidatePath = `${build}/candidate.pptx`;
await (await PresentationFile.exportPptx(deck)).save(candidatePath);
console.log(`Draft written: ${candidatePath}`);

const { finalizePresentation } = await import(pathToFileURL(path.join(skill, 'container_tools/artifact_tool_utils.mjs')).href);
const result = await finalizePresentation({
  workspaceDir: root,
  candidatePath,
  finalPath,
  pythonExecutable: python,
  integrityValidatorPath: path.join(skill, 'container_tools/inspect_presentation_package_integrity.py'),
  layoutValidatorPath: path.join(skill, 'container_tools/inspect_presentation_layout_geometry.py'),
  layoutArgs: ['--expected-slide-size-emu', '15240000,8572500', '--validate-bullet-geometry', '--validate-heading-fit'],
  requiredNativeTableOwnerSlides: [],
  fontPolicy: {
    basis: 'reference',
    families: ['Microsoft YaHei'],
    referencePath: source,
    referenceSha256: '5aba27e6d14e3b378ebd60fc8fbaf5aa46356577cfb07c7c33c930fc3605853d',
  },
  verifyArtifactToolImport: true,
  receiptPath: `${build}/validation.json`,
});
console.log(JSON.stringify(result));
