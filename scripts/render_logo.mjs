#!/usr/bin/env node
/**
 * SkyForge 品牌素材渲染脚本
 *
 * 将 docs/branding/*.svg 渲染为 PNG，适配 HackQuest 提交要求
 * （图片规格：500x300 或 1280x720）。
 *
 * 用法:  node render_logo.mjs   （在 scripts/ 目录下）
 *
 * 注意: 500x300 变体在 16:9 源上做等宽裁切，
 *       已用 PIL 预生成:  docs/branding/skyforge_banner_500x300.png
 */

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { Resvg } from "@resvg/resvg-js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const brandingDir = path.resolve(__dirname, "..", "docs", "branding");

function render(svgFile, outPng, width, height) {
	const svg = fs.readFileSync(path.join(brandingDir, svgFile), "utf8");
	const resvg = new Resvg(svg, {
		fitTo: { mode: "width", value: width },
	});
	const png = resvg.render().asPng();
	fs.writeFileSync(path.join(brandingDir, outPng), png);
	console.log(
		`✔ ${outPng}  (${width}x${height}, ${(png.length / 1024).toFixed(0)} KB)`,
	);
}

render("skyforge_logo.svg", "skyforge_logo_1024.png", 1024, 1024);
render("skyforge_banner.svg", "skyforge_banner_1280x720.png", 1280, 720);
