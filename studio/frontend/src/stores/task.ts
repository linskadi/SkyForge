import { getTaskMessages } from "@/services/taskApi";
import { cancelTask as cancelTaskAPI } from "@/services/taskApi";
import { AgentType } from "@/utils/enum";
import type {
	CodeGenMessage,
	ContractGenMessage,
	InterpreterMessage,
	Message,
	RequirementParserMessage,
	ReviewerMessage,
	UserMessage,
} from "@/utils/response";
import { TaskWebSocket } from "@/utils/websocket";
import { defineStore } from "pinia";
import { computed, ref } from "vue";

/** 任务管理 Store */
export const useTaskStore = defineStore("task", () => {
	// ---- State ----

	/** 按任务ID分组的消息记录 */
	const messagesByTask = ref<Record<string, Message[]>>({});

	/** 当前活跃的任务ID */
	const currentTaskId = ref<string | null>(null);

	/** 当前任务的消息列表（计算属性） */
	const messages = computed<Message[]>(() => {
		if (!currentTaskId.value) {
			return [];
		}
		return messagesByTask.value[currentTaskId.value] ?? [];
	});
	/** 已处理的消息ID集合（用于去重） */
	const seenMessageIdsByTask = new Map<string, Set<string>>();

	/** WebSocket 实例 */
	let ws: TaskWebSocket | null = null;

	/** WebSocket 连接状态 */
	const wsStatus = ref<
		"connecting" | "connected" | "disconnected" | "reconnecting"
	>("disconnected");

	/** 任务是否正在运行 */
	const isRunning = ref(false);

	// ---- Helpers ----

	/** 获取消息时间戳 */
	function getMessageTimestamp(message: Message): number | null {
		if (!message.created_at) {
			return null;
		}
		const timestamp = Date.parse(message.created_at);
		return Number.isNaN(timestamp) ? null : timestamp;
	}

	/** 按时间戳排序消息 */
	function sortMessages(items: Message[]) {
		return [...items].sort((left, right) => {
			const leftTs = getMessageTimestamp(left);
			const rightTs = getMessageTimestamp(right);
			if (leftTs == null || rightTs == null || leftTs === rightTs) {
				return 0;
			}
			return leftTs - rightTs;
		});
	}

	/** 类型守卫：判断是否为有效的消息对象 */
	function isMessagePayload(payload: unknown): payload is Message {
		if (!payload || typeof payload !== "object") {
			return false;
		}
		const msgType = Reflect.get(payload, "msg_type");
		return (
			typeof Reflect.get(payload, "id") === "string" &&
			typeof msgType === "string" &&
			["system", "agent", "user", "tool"].includes(msgType)
		);
	}

	/** 设置当前活跃任务 */
	function setCurrentTask(taskId: string) {
		currentTaskId.value = taskId;
		if (typeof window !== "undefined") {
			window.sessionStorage.setItem("currentTaskId", taskId);
		}
	}

	/** 确保任务的消息桶存在 */
	function ensureTaskBucket(taskId: string) {
		if (!messagesByTask.value[taskId]) {
			messagesByTask.value[taskId] = [];
		}
		if (!seenMessageIdsByTask.has(taskId)) {
			seenMessageIdsByTask.set(taskId, new Set());
		}
	}

	/** 追加消息（自动去重和排序） */
	function appendMessage(taskId: string, message: Message) {
		ensureTaskBucket(taskId);
		const seenIds = seenMessageIdsByTask.get(taskId);
		if (message.id && seenIds?.has(message.id)) {
			messagesByTask.value[taskId] = sortMessages(
				messagesByTask.value[taskId].map((existing) =>
					existing.id === message.id ? message : existing,
				),
			);
			return;
		}
		if (message.id) {
			seenIds?.add(message.id);
		}
		messagesByTask.value[taskId] = sortMessages([
			...messagesByTask.value[taskId],
			message,
		]);
	}

	/** 合并历史消息（用于加载历史记录） */
	function mergeMessages(taskId: string, incomingMessages: Message[]) {
		ensureTaskBucket(taskId);
		const existingMessages = messagesByTask.value[taskId];
		const mergedById = new Map<string, Message>();

		for (const message of [...existingMessages, ...incomingMessages]) {
			if (!message.id) {
				continue;
			}
			mergedById.set(message.id, message);
		}

		const mergedMessages = Array.from(mergedById.values());
		messagesByTask.value[taskId] = sortMessages(mergedMessages);
		seenMessageIdsByTask.set(
			taskId,
			new Set(mergedMessages.map((message) => message.id)),
		);
	}

	// ---- Actions ----

	/** 连接 WebSocket 接收实时消息 */
	function connectWebSocket(taskId: string) {
		if (ws) {
			ws.close();
			ws = null;
		}
		setCurrentTask(taskId);
		ensureTaskBucket(taskId);
		isRunning.value = true;

		const baseUrl = import.meta.env.VITE_WS_URL;
		const wsUrl = `${baseUrl}/task/${taskId}`;

		ws = new TaskWebSocket(
			wsUrl,
			(data) => {
				if (!isMessagePayload(data)) {
					console.warn("忽略非标准任务消息:", data);
					return;
				}
				appendMessage(taskId, data);
				// 检测任务完成/停止/失败消息
				if (data.msg_type === "system") {
					const msgType = Reflect.get(data, "type");
					if (
						msgType === "success" ||
						msgType === "warning" ||
						msgType === "error"
					) {
						isRunning.value = false;
					}
				}
			},
			(status) => {
				wsStatus.value = status;
			},
		);
		ws.connect();
	}

	/** 加载任务的历史消息 */
	async function loadTaskMessages(taskId: string) {
		setCurrentTask(taskId);
		ensureTaskBucket(taskId);
		try {
			const messages = await getTaskMessages(taskId);
			const validMessages = (messages ?? []).filter(isMessagePayload);
			mergeMessages(taskId, validMessages);
		} catch (error) {
			console.error("加载任务历史消息失败:", error);
		}
	}

	/** 关闭 WebSocket 连接 */
	function closeWebSocket() {
		ws?.close();
		ws = null;
	}

	/** 取消正在运行的任务 */
	async function stopTask(taskId: string) {
		try {
			const data = await cancelTaskAPI(taskId);
			if (data.success) {
				isRunning.value = false;
			}
			return data;
		} catch (error) {
			console.error("取消任务失败:", error);
			return { success: false, message: "取消请求失败" };
		}
	}

	/** 添加用户消息 */
	function addUserMessage(content: string) {
		const taskId = currentTaskId.value ?? "local";
		appendMessage(taskId, {
			id: Date.now().toString(),
			msg_type: "user",
			content: content,
		} as UserMessage);
	}

	/** 下载消息为 JSON 文件 */
	function downloadMessages() {
		const dataStr = `data:text/json;charset=utf-8,${encodeURIComponent(JSON.stringify(messages.value, null, 2))}`;
		const downloadAnchorNode = document.createElement("a");
		downloadAnchorNode.setAttribute("href", dataStr);
		downloadAnchorNode.setAttribute(
			"download",
			`${currentTaskId.value ?? "task"}-messages.json`,
		);
		document.body.appendChild(downloadAnchorNode);
		downloadAnchorNode.click();
		downloadAnchorNode.remove();
	}

	// ---- Computed ----

	/** 聊天消息列表（用户、CODE-Gen Agent、系统消息） */
	const chatMessages = computed(() =>
		messages.value.filter((msg) => {
			if (
				msg.msg_type === "agent" &&
				msg.agent_type === AgentType.CODE_GEN &&
				msg.content != null &&
				msg.content !== ""
			) {
				return true;
			}
			if (msg.msg_type === "user") {
				return true;
			}
			if (msg.msg_type === "system") {
				return true;
			}
			return false;
		}),
	);

	/** 需求解析消息列表 (REQ-Parser) */
	const reqParserMessages = computed(() =>
		messages.value.filter(
			(msg): msg is RequirementParserMessage =>
				msg.msg_type === "agent" &&
				msg.agent_type === AgentType.REQ_PARSER &&
				msg.content != null,
		),
	);

	/** 合约生成消息列表 (CON-Gen) */
	const conGenMessages = computed(() =>
		messages.value.filter(
			(msg): msg is ContractGenMessage =>
				msg.msg_type === "agent" &&
				msg.agent_type === AgentType.CON_GEN &&
				msg.content != null,
		),
	);

	/** 代码生成消息列表 (CODE-Gen) */
	const codeGenMessages = computed(() =>
		messages.value.filter(
			(msg): msg is CodeGenMessage =>
				msg.msg_type === "agent" &&
				msg.agent_type === AgentType.CODE_GEN &&
				msg.content != null,
		),
	);

	/** 修复消息列表 (REPAIR) */
	const reviewerMessages = computed(() =>
		messages.value.filter(
			(msg): msg is ReviewerMessage =>
				msg.msg_type === "agent" &&
				msg.agent_type === AgentType.REPAIR &&
				msg.content != null,
		),
	);

	/** 代码执行工具消息列表 */
	const interpreterMessage = computed(() =>
		messages.value.filter(
			(msg): msg is InterpreterMessage =>
				msg.msg_type === "tool" &&
				"tool_name" in msg &&
				msg.tool_name === "execute_code",
		),
	);

	/** 从最新代码生成消息中提取文件列表 */
	const files = computed(() => {
		// 反向遍历消息找到最新的文件列表
		for (let i = codeGenMessages.value.length - 1; i >= 0; i--) {
			const msg = codeGenMessages.value[i];
			if (
				"files" in msg &&
				msg.files &&
				Array.isArray(msg.files) &&
				msg.files.length > 0
			) {
				return msg.files;
			}
		}
		// 如果没有找到文件列表，返回空数组
		return [];
	});

	// 初始化连接
	// 如果需要自动连接，可以在这里添加代码
	// 例如：connectWebSocket('default')

	return {
		messages,
		wsStatus,
		isRunning,
		chatMessages,
		reqParserMessages,
		conGenMessages,
		codeGenMessages,
		reviewerMessages,
		interpreterMessage,
		files,
		loadTaskMessages,
		connectWebSocket,
		closeWebSocket,
		stopTask,
		downloadMessages,
		addUserMessage,
	};
});
