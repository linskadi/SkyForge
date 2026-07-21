import { ref } from "vue";

export type FaultType =
	| "sensor_stuck"
	| "sensor_offset"
	| "sensor_noise"
	| "actuator_saturation"
	| "communication_delay"
	| "software_hang";

export interface FaultInfo {
	type: FaultType;
	name: string;
	description: string;
}

export function useSimulation() {
	const faultInjected = ref(false);
	const selectedFaultType = ref<FaultType | null>("sensor_stuck");

	const faultTypes: FaultInfo[] = [
		{
			type: "sensor_stuck",
			name: "传感器卡死",
			description: "传感器输出保持固定值，检测到契约违约",
		},
		{
			type: "sensor_offset",
			name: "传感器偏置",
			description: "传感器输出叠加固定偏置，超出正常范围",
		},
		{
			type: "sensor_noise",
			name: "传感器噪声",
			description: "传感器输出叠加高频噪声，影响滤波效果",
		},
		{
			type: "actuator_saturation",
			name: "执行器饱和",
			description: "执行器输出达到最大值后保持不变",
		},
		{
			type: "communication_delay",
			name: "通信延迟",
			description: "输出延迟若干步，时序偏差",
		},
		{
			type: "software_hang",
			name: "软件挂起",
			description: "软件执行挂起，输出保持上一拍值",
		},
	];

	function toggleFaultInjection(): void {
		faultInjected.value = !faultInjected.value;
		if (faultInjected.value && !selectedFaultType.value) {
			selectedFaultType.value = "sensor_stuck";
		}
		if (!faultInjected.value) {
			selectedFaultType.value = null;
		}
	}

	function setFaultType(type: FaultType): void {
		selectedFaultType.value = type;
	}

	// 确定性噪声函数（替代 Math.random 避免无限重渲染）
	function deterministicNoise(seed: number): number {
		const x = Math.sin(seed * 12.9898 + seed * 78.233) * 43758.5453;
		return (x - Math.floor(x)) * 2 - 1; // 返回 -1 到 1 之间的值
	}

	function wavePoints(
		values: number[] | undefined,
		isInput: boolean = false,
	): string {
		if (!values?.length) return "";
		const sample = values.filter((_, index) => index % 4 === 0);
		return sample
			.map((value, index) => {
				const x = (index / Math.max(1, sample.length - 1)) * 520;
				let adjusted = value;
				if (
					faultInjected.value &&
					selectedFaultType.value &&
					index > 18 &&
					index < 29
				) {
					switch (selectedFaultType.value) {
						case "sensor_stuck":
							adjusted = isInput ? 65535 : 65535;
							break;
						case "sensor_offset":
							adjusted = isInput
								? Math.min(65535, value + 15000)
								: Math.min(65535, value + 15000);
							break;
						case "sensor_noise":
							if (isInput) {
								// 使用确定性噪声替代 Math.random
								adjusted = value + deterministicNoise(index) * 5000;
							}
							break;
						case "actuator_saturation":
							adjusted = Math.min(65535, value * 1.5);
							break;
						case "communication_delay":
							if (!isInput && index > 22) {
								const delayIndex = Math.max(0, index - 4);
								adjusted = values[delayIndex * 4] ?? value;
							}
							break;
						case "software_hang":
							adjusted = isInput ? value : 65535;
							break;
					}
				}
				const y = 165 - (Math.min(65535, Math.max(0, adjusted)) / 65535) * 150;
				return `${x.toFixed(1)},${y.toFixed(1)}`;
			})
			.join(" ");
	}

	function resetSimulation(): void {
		faultInjected.value = false;
		selectedFaultType.value = "sensor_stuck";
	}

	return {
		faultInjected,
		selectedFaultType,
		faultTypes,
		toggleFaultInjection,
		setFaultType,
		wavePoints,
		resetSimulation,
	};
}
