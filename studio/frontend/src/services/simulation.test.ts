import { describe, expect, it } from "vitest";
import { computeStats, genSineInput, lowpassFilter } from "./simulation";

describe("genSineInput", () => {
	it("generates correct number of steps", () => {
		const wave = genSineInput(100);
		expect(wave).toHaveLength(100);
	});

	it("values are within expected ADC range", () => {
		const wave = genSineInput(200);
		for (const v of wave) {
			expect(v).toBeGreaterThanOrEqual(0);
			expect(v).toBeLessThanOrEqual(65535);
		}
	});

	it("center value is approximately ADC_CENTER (32768)", () => {
		const wave = genSineInput(1000);
		const avg = wave.reduce((s, v) => s + v, 0) / wave.length;
		expect(avg).toBeGreaterThan(32000);
		expect(avg).toBeLessThan(34000);
	});
});

describe("lowpassFilter", () => {
	it("produces same-length output", () => {
		const input = [100, 200, 300, 400, 500];
		const output = lowpassFilter(input, 0.1);
		expect(output).toHaveLength(input.length);
	});

	it("smooths the signal (output variance < input variance)", () => {
		const input = [0, 10000, 0, 10000, 0, 10000];
		const output = lowpassFilter(input, 0.1);
		const inputVar = variance(input);
		const outputVar = variance(output);
		expect(outputVar).toBeLessThan(inputVar);
	});

	it("first output equals first input (alpha=1 passthrough)", () => {
		const input = [100, 200, 300];
		const output = lowpassFilter(input, 1.0);
		expect(output[0]).toBe(100);
	});

	it("alpha=0 produces all zeros", () => {
		const input = [100, 200, 300];
		const output = lowpassFilter(input, 0);
		expect(output).toEqual([0, 0, 0]);
	});
});

describe("computeStats", () => {
	it("computes correct total_steps", () => {
		const input = [1, 2, 3, 4, 5];
		const output = [2, 4, 6, 8, 10];
		const stats = computeStats(input, output);
		expect(stats.total_steps).toBe(5);
	});

	it("computes correct input range", () => {
		const input = [10, 50, 30];
		const output = [20, 60, 40];
		const stats = computeStats(input, output);
		expect(stats.input_range).toEqual([10, 50]);
	});

	it("computes correct output range", () => {
		const input = [10, 50, 30];
		const output = [20, 60, 40];
		const stats = computeStats(input, output);
		expect(stats.output_range).toEqual([20, 60]);
		expect(stats.output_max).toBe(60);
		expect(stats.output_min).toBe(20);
	});

	it("computes correct output_mean", () => {
		const input = [1, 2];
		const output = [10, 20];
		const stats = computeStats(input, output);
		expect(stats.output_mean).toBe(15);
	});
});

function variance(arr: number[]): number {
	const mean = arr.reduce((s, v) => s + v, 0) / arr.length;
	return arr.reduce((s, v) => s + (v - mean) ** 2, 0) / arr.length;
}
