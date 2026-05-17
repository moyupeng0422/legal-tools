#!/usr/bin/env node
/**
 * 法律问题研究报告 DOCX 生成器
 *
 * 用法: node generate_report.js <input.json> [output.docx]
 */

/*
SCHEMA:
{
  "basicInfo": {
    "研究主题": "研究主题关键词",
    "研究日期": "2026-05-17",
    "问题类型": "法条适用/侵权判定/权利范围/程序问题",
    "涉及法律领域": "知识产权/合同/劳动等",
    "分析模式": "Full"
  },
  "legalBasis": [
    {
      "name": "法规名称",
      "article": "第X条第X款",
      "content": "法条原文",
      "source": "flk-npc",
      "status": "现行有效"
    }
  ],
  "caseRules": [
    {
      "title": "裁判规则标题",
      "court": "审理法院",
      "date": "裁判日期",
      "keyPoint": "裁判要旨",
      "source": "rmfyalk",
      "level": "指导性案例/参考案例/一般案例"
    }
  ],
  "analysis": {
    "legalPosition": "法律立场分析",
    "judicialPractice": "司法实践分析",
    "disputes": "争议焦点",
    "riskAssessment": "风险评估"
  },
  "verifyItems": ["需要进一步验证的事项"],
  "conclusion": "综合结论",
  "disclaimer": "免责声明（可选，有默认值）"
}
*/

const fs = require("fs");
const { execSync } = require("child_process");

// 自动解析全局 node_modules 路径
try { require.resolve("docx"); } catch {
  try {
    const prefix = execSync("npm config get prefix", { encoding: "utf-8" }).trim();
    const globalPath = require("path").join(prefix, "lib", "node_modules");
    module.paths.unshift(globalPath);
  } catch { /* ignore */ }
}

const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, HeadingLevel, BorderStyle, WidthType,
  ShadingType, VerticalAlign, PageNumber
} = require("docx");

// ── 常量 ──
const FONT = "仿宋";
const FONT_EN = "Times New Roman";
const SIZE_TITLE = 36;
const SIZE_H1 = 30;
const SIZE_H2 = 28;
const SIZE_BODY = 24;
const SIZE_SMALL = 21;
const LINE_SPACING = 360;
const COLOR_PRIMARY = "1A3C6E";
const COLOR_HEADER_BG = "E8EDF3";
const COLOR_SOURCE = "666666";
const DEFAULT_DISCLAIMER = "本报告基于公开法律数据库检索结果生成，受数据库覆盖范围、时效性和检索关键词限制。报告中的法律分析供研究参考，不构成法律意见。具体法律问题请结合案件全部事实和证据，由执业律师出具正式法律意见。";

const thinBorder = { style: BorderStyle.SINGLE, size: 1, color: "BBBBBB" };
const cellBorders = { top: thinBorder, bottom: thinBorder, left: thinBorder, right: thinBorder };

// ── 辅助函数 ──
function bodyPara(children, options = {}) {
  return new Paragraph({
    spacing: { line: LINE_SPACING, before: options.before || 0, after: options.after || 0 },
    indent: options.indent,
    alignment: options.alignment || AlignmentType.JUSTIFIED,
    children: Array.isArray(children) ? children : [children],
  });
}

function textRun(text, options = {}) {
  return new TextRun({
    text,
    font: { name: FONT, eastAsia: FONT, ascii: FONT_EN, hAnsi: FONT_EN },
    size: options.size || SIZE_BODY,
    bold: options.bold || false,
    color: options.color || "000000",
    italics: options.italics || false,
  });
}

function h1(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    spacing: { before: 300, after: 200, line: LINE_SPACING },
    children: [textRun(text, { size: SIZE_H1, bold: true, color: COLOR_PRIMARY })],
  });
}

function h2(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    spacing: { before: 200, after: 100, line: LINE_SPACING },
    children: [textRun(text, { size: SIZE_H2, bold: true, color: COLOR_PRIMARY })],
  });
}

function makeInfoTable(info) {
  const keys = Object.keys(info);
  return new Table({
    columnWidths: [2400, 6960],
    rows: keys.map(key =>
      new TableRow({
        children: [
          new TableCell({
            borders: cellBorders,
            width: { size: 2400, type: WidthType.DXA },
            shading: { fill: COLOR_HEADER_BG, type: ShadingType.CLEAR },
            verticalAlign: VerticalAlign.CENTER,
            children: [bodyPara(textRun(key, { bold: true }), { alignment: AlignmentType.CENTER })],
          }),
          new TableCell({
            borders: cellBorders,
            width: { size: 6960, type: WidthType.DXA },
            verticalAlign: VerticalAlign.CENTER,
            children: [bodyPara(textRun(info[key]))],
          }),
        ],
      })
    ),
  });
}

function makeLawTable(items) {
  if (!items || items.length === 0) return [];
  return [new Table({
    columnWidths: [2400, 1800, 3000, 1600],
    rows: [
      new TableRow({
        children: ["法规名称", "条款", "来源", "时效性"].map(label =>
          new TableCell({
            borders: cellBorders,
            shading: { fill: COLOR_HEADER_BG, type: ShadingType.CLEAR },
            verticalAlign: VerticalAlign.CENTER,
            children: [bodyPara(textRun(label, { bold: true, size: SIZE_SMALL }), { alignment: AlignmentType.CENTER })],
          })
        ),
      }),
      ...items.map(item =>
        new TableRow({
          children: [
            new TableCell({ borders: cellBorders, children: [bodyPara(textRun(item.name, { size: SIZE_SMALL }))] }),
            new TableCell({ borders: cellBorders, children: [bodyPara(textRun(item.article || "", { size: SIZE_SMALL }))] }),
            new TableCell({ borders: cellBorders, children: [bodyPara(textRun(item.source || "", { size: SIZE_SMALL, color: COLOR_SOURCE }))] }),
            new TableCell({ borders: cellBorders, children: [bodyPara(textRun(item.status || "", { size: SIZE_SMALL }))] }),
          ],
        })
      ),
    ],
  })];
}

function makeCaseTable(items) {
  if (!items || items.length === 0) return [];
  return [new Table({
    columnWidths: [3200, 2000, 1400, 1400, 1400],
    rows: [
      new TableRow({
        children: ["标题", "法院", "日期", "来源", "层级"].map(label =>
          new TableCell({
            borders: cellBorders,
            shading: { fill: COLOR_HEADER_BG, type: ShadingType.CLEAR },
            verticalAlign: VerticalAlign.CENTER,
            children: [bodyPara(textRun(label, { bold: true, size: SIZE_SMALL }), { alignment: AlignmentType.CENTER })],
          })
        ),
      }),
      ...items.map(item =>
        new TableRow({
          children: [
            new TableCell({ borders: cellBorders, children: [bodyPara(textRun(item.title, { size: SIZE_SMALL }))] }),
            new TableCell({ borders: cellBorders, children: [bodyPara(textRun(item.court || "", { size: SIZE_SMALL }))] }),
            new TableCell({ borders: cellBorders, children: [bodyPara(textRun(item.date || "", { size: SIZE_SMALL }))] }),
            new TableCell({ borders: cellBorders, children: [bodyPara(textRun(item.source || "", { size: SIZE_SMALL, color: COLOR_SOURCE }))] }),
            new TableCell({ borders: cellBorders, children: [bodyPara(textRun(item.level || "", { size: SIZE_SMALL }))] }),
          ],
        })
      ),
    ],
  })];
}

// ── 主函数 ──
async function generate(inputPath, outputPath) {
  const data = JSON.parse(fs.readFileSync(inputPath, "utf-8"));
  const children = [];

  // ═══ 标题 ═══
  children.push(new Paragraph({
    spacing: { before: 400, after: 300, line: LINE_SPACING },
    alignment: AlignmentType.CENTER,
    children: [textRun("法律问题研究报告", { size: SIZE_TITLE, bold: true, color: COLOR_PRIMARY })],
  }));

  // ═══ 一、基本信息 ═══
  children.push(h1("一、基本信息"));
  children.push(makeInfoTable(data.basicInfo));

  // ═══ 二、法律依据 ═══
  if (data.legalBasis && data.legalBasis.length > 0) {
    children.push(h1("二、法律依据"));
    children.push(...makeLawTable(data.legalBasis));

    // 法条原文
    for (let i = 0; i < data.legalBasis.length; i++) {
      const law = data.legalBasis[i];
      if (law.content) {
        children.push(bodyPara([
          textRun(`${law.name} ${law.article}`, { bold: true, size: SIZE_SMALL }),
        ], { before: 120, after: 40 }));
        children.push(bodyPara(
          textRun(law.content, { size: SIZE_SMALL }),
          { before: 0, after: 80, indent: { left: 480 } }
        ));
      }
    }
  }

  // ═══ 三、裁判规则与案例 ═══
  if (data.caseRules && data.caseRules.length > 0) {
    children.push(h1("三、裁判规则与案例"));
    children.push(...makeCaseTable(data.caseRules));

    for (let i = 0; i < data.caseRules.length; i++) {
      const rule = data.caseRules[i];
      if (rule.keyPoint) {
        children.push(bodyPara([
          textRun(`${i + 1}. ${rule.title}`, { bold: true }),
        ], { before: 120, after: 40 }));
        children.push(bodyPara(
          textRun(`裁判要旨：${rule.keyPoint}`, { size: SIZE_SMALL }),
          { before: 0, after: 80, indent: { left: 480 } }
        ));
      }
    }
  }

  // ═══ 四、综合分析 ═══
  if (data.analysis) {
    children.push(h1("四、综合分析"));

    const sections = [
      ["法律立场", data.analysis.legalPosition],
      ["司法实践", data.analysis.judicialPractice],
      ["争议焦点", data.analysis.disputes],
      ["风险评估", data.analysis.riskAssessment],
    ];

    for (const [label, content] of sections) {
      if (!content) continue;
      children.push(h2(label));
      const paragraphs = content.split("\n").filter(s => s.trim());
      for (const p of paragraphs) {
        children.push(bodyPara(textRun(p), { before: 60 }));
      }
    }
  }

  // ═══ 五、综合结论 ═══
  if (data.conclusion) {
    children.push(h1("五、综合结论"));
    const paragraphs = data.conclusion.split("\n").filter(s => s.trim());
    for (const p of paragraphs) {
      children.push(bodyPara(textRun(p), { before: 60 }));
    }
  }

  // ═══ 六、待验证事项 ═══
  if (data.verifyItems && data.verifyItems.length > 0) {
    children.push(h1("六、待验证事项"));
    for (const item of data.verifyItems) {
      children.push(bodyPara([
        textRun("[verify] ", { bold: true, color: "CC7700" }),
        textRun(item),
      ], { before: 60 }));
    }
  }

  // ═══ 七、免责声明 ═══
  const disclaimerIdx = data.verifyItems && data.verifyItems.length > 0 ? "八" : "六";
  children.push(h1(`${disclaimerIdx}、免责声明`));
  children.push(bodyPara(
    textRun(data.disclaimer || DEFAULT_DISCLAIMER, { size: SIZE_SMALL, color: "666666" }),
    { before: 60 }
  ));

  // ═══ 构建文档 ═══
  const doc = new Document({
    styles: {
      default: { document: { run: { font: FONT, size: SIZE_BODY } } },
      paragraphStyles: [
        {
          id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
          run: { size: SIZE_H1, bold: true, color: COLOR_PRIMARY, font: FONT },
          paragraph: { spacing: { before: 300, after: 200 }, outlineLevel: 0 },
        },
        {
          id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
          run: { size: SIZE_H2, bold: true, color: COLOR_PRIMARY, font: FONT },
          paragraph: { spacing: { before: 200, after: 100 }, outlineLevel: 1 },
        },
      ],
    },
    sections: [{
      properties: {
        page: { margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 } },
      },
      headers: {
        default: new Header({
          children: [new Paragraph({
            alignment: AlignmentType.RIGHT,
            children: [textRun("法律问题研究报告", { size: SIZE_SMALL, color: "999999" })],
          })],
        }),
      },
      footers: {
        default: new Footer({
          children: [new Paragraph({
            alignment: AlignmentType.CENTER,
            children: [
              textRun("第 ", { size: SIZE_SMALL, color: "999999" }),
              new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: SIZE_SMALL, color: "999999" }),
              textRun(" 页 / 共 ", { size: SIZE_SMALL, color: "999999" }),
              new TextRun({ children: [PageNumber.TOTAL_PAGES], font: FONT, size: SIZE_SMALL, color: "999999" }),
              textRun(" 页", { size: SIZE_SMALL, color: "999999" }),
            ],
          })],
        }),
      },
      children,
    }],
  });

  const buffer = await Packer.toBuffer(doc);
  fs.writeFileSync(outputPath, buffer);
  console.log(`报告已生成: ${outputPath}`);
}

// ── 入口 ──
const args = process.argv.slice(2);
if (args.length < 1) {
  console.error("用法: node generate_report.js <input.json> [output.docx]");
  process.exit(1);
}
const inputFile = args[0];
const outputFile = args[1] || inputFile.replace(/\.json$/, "") + "_report.docx";

generate(inputFile, outputFile).catch(err => {
  console.error("生成失败:", err.message);
  process.exit(1);
});
