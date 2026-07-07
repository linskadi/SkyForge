/**
 * Task API — unified replacement for src/apis/*
 * ====================================================================
 * Replaces: commonApi.ts, filesApi.ts, submitModelingApi.ts, apiKeyApi.ts
 * All functions use the unified client from ./client.ts
 * No axios dependency. Returns data directly (no .data wrapper).
 */

import { getJSON, postJSON, postFormData } from "./client";
import type { Message } from "@/utils/response";

// ---- Health & Status ----

/** 健康检查 */
export function getHelloWorld(): Promise<{ message: string }> {
  return getJSON("/");
}

/** 获取审查状态 */
export function getReviewerStatus(): Promise<{ reviewer_status: string[] }> {
  return getJSON("/reviewer_status");
}

/** 获取后端和 Redis 服务状态 */
export function getServiceStatus(): Promise<{
  backend: { status: string; message: string };
  redis: { status: string; message: string };
}> {
  return getJSON("/status");
}

// ---- Task Messages & Control ----

/**
 * 获取任务的历史消息
 * @param task_id 任务ID
 */
export function getTaskMessages(task_id: string): Promise<Message[]> {
  return getJSON(`/messages?task_id=${encodeURIComponent(task_id)}`);
}

/**
 * 打开工作目录
 * @param task_id 任务ID
 */
export function openFolderAPI(task_id: string): Promise<{ message: string }> {
  return getJSON(`/open_folder?task_id=${encodeURIComponent(task_id)}`);
}

/**
 * 提交样例任务
 * @param example_id 样例ID
 * @param source 来源
 */
export function exampleAPI(
  example_id: string,
  source: string,
): Promise<{ task_id: string; status: string }> {
  return postJSON("/example", { example_id, source });
}

/**
 * 取消正在运行的任务
 * @param task_id 任务ID
 */
export function cancelTask(
  task_id: string,
): Promise<{ success: boolean; message: string }> {
  return postJSON(`/pipeline/${task_id}/cancel`);
}

// ---- Files ----

/**
 * 获取任务工作区文件列表
 * @param task_id 任务ID
 */
export function getFiles(
  task_id: string,
): Promise<{
  files: { filename: string; file_type: string }[];
}> {
  return getJSON(`/files?task_id=${encodeURIComponent(task_id)}`);
}

/**
 * 获取单个文件下载链接
 * @param task_id 任务ID
 * @param filename 文件名
 */
export function getFileDownloadUrl(
  task_id: string,
  filename: string,
): Promise<{ download_url: string }> {
  return getJSON(
    `/download_url?task_id=${encodeURIComponent(task_id)}&filename=${encodeURIComponent(filename)}`,
  );
}

/**
 * 获取所有文件压缩包下载链接
 * @param task_id 任务ID
 */
export function getAllFilesDownloadUrl(
  task_id: string,
): Promise<{ download_url: string }> {
  return getJSON(`/download_all_url?task_id=${encodeURIComponent(task_id)}`);
}

// ---- Modeling Task Submission ----

/**
 * 提交机载软件开发任务
 * @param problem 问题描述
 * @param files 上传的数据文件
 */
export function submitModelingTask(
  problem: {
    ques_all: string;
    comp_template?: string;
    format_output?: string;
  },
  files?: File[],
): Promise<{ task_id: string; status: string }> {
  const formData = new FormData();
  formData.append("ques_all", problem.ques_all);
  formData.append("comp_template", "CHINA");
  formData.append("format_output", problem.format_output || "Markdown");

  if (files) {
    for (const file of files) {
      formData.append("files", file);
    }
  }

  return postFormData("/modeling", formData, 30_000);
}

// ---- API Key Management ----

/** 验证 API Key 请求参数 */
export interface ValidateApiKeyRequest {
  api_key: string;
  base_url?: string;
  model_id: string;
  api_type?: string;
}

/** 验证 API Key 响应 */
export interface ValidateApiKeyResponse {
  valid: boolean;
  message: string;
}

/** 保存 API 配置请求参数 */
export interface SaveApiConfigRequest {
  req_parser: {
    apiKey: string;
    baseUrl: string;
    modelId: string;
    apiType: string;
  };
  con_gen: {
    apiKey: string;
    baseUrl: string;
    modelId: string;
    apiType: string;
  };
  code_gen: {
    apiKey: string;
    baseUrl: string;
    modelId: string;
    apiType: string;
  };
  repair: {
    apiKey: string;
    baseUrl: string;
    modelId: string;
    apiType: string;
  };
  openalex_email: string;
}

/** 验证 OpenAlex Email 请求参数 */
export interface ValidateOpenalexEmailRequest {
  email: string;
}

/** 验证 OpenAlex Email 响应 */
export interface ValidateOpenalexEmailResponse {
  valid: boolean;
  message: string;
}

/**
 * 验证 API Key 是否有效
 * @param params 验证请求参数
 */
export function validateApiKey(
  params: ValidateApiKeyRequest,
): Promise<ValidateApiKeyResponse> {
  return postJSON("/validate-api-key", params);
}

/**
 * 验证 OpenAlex Email 是否有效
 * @param params 验证请求参数
 */
export function validateOpenalexEmail(
  params: ValidateOpenalexEmailRequest,
): Promise<ValidateOpenalexEmailResponse> {
  return postJSON("/validate-openalex-email", params);
}

/**
 * 保存 API 配置到后端
 * @param params API 配置参数
 */
export function saveApiConfig(
  params: SaveApiConfigRequest,
): Promise<{ success: boolean; message: string }> {
  return postJSON("/save-api-config", params);
}
