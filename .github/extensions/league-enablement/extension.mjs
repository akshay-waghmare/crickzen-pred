// Extension: league-enablement
// Audit and wire cricket prediction league models into live Streamlit and desktop launcher.

import { joinSession } from "@github/copilot-sdk/extension";
import * as fs from "fs";
import * as path from "path";
import { execSync } from "child_process";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(__dirname, "../../..");

const session = await joinSession({
    tools: [
        {
            name: "audit_league_model",
            description: "Audits a league model's metrics, configuration, artifacts, and feature store. Uses Python inline check.",
            parameters: {
                type: "object",
                properties: {
                    league: { type: "string", description: "League code (e.g. ntb, bbl, sa20)" },
                    modelDir: { type: "string", description: "Optional path to model directory (relative to repo root)" },
                    featureStoreDir: { type: "string", description: "Optional path to feature store directory" }
                },
                required: ["league"]
            },
            handler: async (args) => {
                const pythonExe = process.platform === "win32" ? ".venv/Scripts/python.exe" : ".venv/bin/python";
                const pythonPath = path.resolve(projectRoot, pythonExe);
                const exe = fs.existsSync(pythonPath) ? pythonPath : "python";
                
                const helperPath = path.join(__dirname, "audit_helper.py");
                let cmd = `"${exe}" "${helperPath}" --league ${args.league}`;
                if (args.modelDir) cmd += ` --model-dir "${args.modelDir}"`;
                if (args.featureStoreDir) cmd += ` --feature-store-dir "${args.featureStoreDir}"`;
                
                try {
                    const output = execSync(cmd, { cwd: projectRoot, encoding: "utf-8" });
                    const res = JSON.parse(output);
                    
                    if (!res.success) {
                        return `### ❌ Audit Failed\n\n${res.error}\n\n**Warnings:**\n${res.warnings.map(w => `- ${w}`).join("\n")}`;
                    }
                    
                    let report = `## 🏏 League Audit Report: ${res.league.toUpperCase()}\n\n`;
                    report += `* **Model Type:** \`${res.model_type}\`\n`;
                    report += `* **Model Directory:** \`${res.model_dir}\`\n`;
                    report += `* **Feature Store:** \`${res.feature_store_dir || "None"}\` (Status: \`${res.feature_store_status}\`)\n\n`;
                    
                    report += `### 📂 Artifact Verification\n`;
                    for (const [art, found] of Object.entries(res.artifacts)) {
                        report += `* \`${art}\`: ${found ? "✅ Present" : "❌ Missing"}\n`;
                    }
                    if (res.feature_store_files) {
                        report += `* \`Feature Store Files\`: ${res.feature_store_files.join(", ")}\n`;
                    }
                    report += `\n`;
                    
                    if (res.calibrator_metadata) {
                        report += `### 🎯 Calibrator Metadata\n`;
                        report += `\`\`\`json\n${JSON.stringify(res.calibrator_metadata, null, 2)}\n\`\`\`\n\n`;
                    }
                    
                    if (res.metrics) {
                        report += `### 📊 Calibration Metrics\n`;
                        if (res.metrics.oof_overall) {
                            report += `#### Overall OOF\n`;
                            report += `* **Brier Raw:** \`${res.metrics.oof_overall.brier_raw?.toFixed(5)}\` | **Calibrated:** \`${res.metrics.oof_overall.brier_calibrated?.toFixed(5)}\`\n`;
                            report += `* **ECE Raw:** \`${res.metrics.oof_overall.ece_raw?.toFixed(5)}\` | **Calibrated:** \`${res.metrics.oof_overall.ece_calibrated?.toFixed(5)}\`\n\n`;
                        }
                        if (res.metrics.oof_by_phase) {
                            report += `#### OOF by Phase (Innings 2)\n`;
                            report += `| Phase | Rows | Raw Brier | Cal Brier | Raw LogLoss | Cal LogLoss |\n`;
                            report += `|---|---|---|---|---|---|\n`;
                            for (const r of res.metrics.oof_by_phase) {
                                report += `| ${r.phase.toUpperCase()} | ${r.n_rows || r.n || "-"} | ${r.oof_brier_raw?.toFixed(5) || r.brier_raw?.toFixed(5)} | ${r.oof_brier_cal?.toFixed(5) || r.brier_cal?.toFixed(5)} | ${r.logloss_raw?.toFixed(5) || "-"} | ${r.logloss_cal?.toFixed(5) || "-"} |\n`;
                            }
                            report += `\n`;
                        }
                        if (res.metrics.oos_by_phase) {
                            report += `#### True OOS by Phase (Innings 2)\n`;
                            report += `| Phase | Rows | Raw Brier | Cal Brier | Raw LogLoss | Cal LogLoss |\n`;
                            report += `|---|---|---|---|---|---|\n`;
                            for (const r of res.metrics.oos_by_phase) {
                                report += `| ${r.phase.toUpperCase()} | ${r.n_rows || r.n || "-"} | ${r.oos_brier_raw?.toFixed(5) || r.brier_raw?.toFixed(5)} | ${r.oos_brier_cal?.toFixed(5) || r.brier_cal?.toFixed(5)} | ${r.logloss_raw?.toFixed(5) || "-"} | ${r.logloss_cal?.toFixed(5) || "-"} |\n`;
                            }
                            report += `\n`;
                        }
                        if (res.metrics.oof_calibration_comparison) {
                            report += `#### OOF Comparison (Key Methods)\n`;
                            report += `| Method | Segment | Brier | ECE | LogLoss | Rows |\n`;
                            report += `|---|---|---|---|---|---|\n`;
                            for (const r of res.metrics.oof_calibration_comparison) {
                                report += `| ${r.method} | ${r.segment} | ${r.brier?.toFixed(5)} | ${r.ece?.toFixed(5)} | ${r.logloss?.toFixed(5)} | ${r.n_samples} |\n`;
                            }
                            report += `\n`;
                        }
                    }
                    
                    if (res.warnings && res.warnings.length > 0) {
                        report += `### ⚠️ Warnings / Structural Issues\n`;
                        report += res.warnings.map(w => `- ${w}`).join("\n") + "\n\n";
                    }
                    
                    return report;
                } catch (e) {
                    return `### ❌ Audit Execution Failure\n\n${e.message}`;
                }
            }
        },
        {
            name: "wire_league_live",
            description: "Automatically wires a new league into scripts/launcher.py, dashboard/app/config.py, and the live Streamlit app.",
            parameters: {
                type: "object",
                properties: {
                    leagueKey: { type: "string", description: "League key in uppercase (e.g. NTB, SA20)" },
                    leagueCode: { type: "string", description: "Internal league code in lowercase (e.g. ntb, sa20)" },
                    modelDir: { type: "string", description: "Path to model folder (e.g. models/ntb_v1_phase)" },
                    featureStoreDir: { type: "string", description: "Path to feature store folder (e.g. data/ntb_feature_store_v1)" },
                    outputJson: { type: "string", description: "Predictor live state output JSON file (e.g. data/ntb_live_ml.json)" },
                    urlPatterns: { type: "array", items: { type: "string" }, description: "CREX URL pattern list (e.g. ['vitality-blast', 't20-blast'])" }
                },
                required: ["leagueKey", "leagueCode", "modelDir", "featureStoreDir", "outputJson", "urlPatterns"]
            },
            handler: async (args) => {
                const results = [];
                
                // 1. Wire scripts/launcher.py
                const launcherPath = path.join(projectRoot, "scripts/launcher.py");
                if (fs.existsSync(launcherPath)) {
                    let content = fs.readFileSync(launcherPath, "utf-8");
                    let modified = false;
                    
                    // Insert into LEAGUE_CONFIGS
                    if (!content.includes(`"${args.leagueKey}":`)) {
                        const marker = "LEAGUE_CONFIGS = {";
                        const idx = content.indexOf(marker);
                        if (idx !== -1) {
                            const configEntry = `\n    "${args.leagueKey}": {\n        "league": "${args.leagueCode}",\n        "model_dir": "${args.modelDir}",\n        "feature_store_dir": "${args.featureStoreDir}",\n        "output_json": "${args.outputJson}",\n        "states_dir": "data/match_states/${args.leagueCode}",\n    },`;
                            content = content.slice(0, idx + marker.length) + configEntry + content.slice(idx + marker.length);
                            modified = true;
                        }
                    }
                    
                    // Insert into _URL_LEAGUE_PATTERNS
                    if (!content.includes(`"${args.leagueKey}"`) && args.urlPatterns.length > 0) {
                        const marker = "_URL_LEAGUE_PATTERNS: list[tuple[str, str]] = [";
                        const idx = content.indexOf(marker);
                        if (idx !== -1) {
                            const patternEntries = args.urlPatterns.map(p => `\n    (r"${p}", "${args.leagueKey}"),`).join("");
                            content = content.slice(0, idx + marker.length) + patternEntries + content.slice(idx + marker.length);
                            modified = true;
                        }
                    }
                    
                    if (modified) {
                        fs.writeFileSync(launcherPath, content, "utf-8");
                        results.push("✅ Successfully updated scripts/launcher.py configurations");
                    } else {
                        results.push("ℹ️ scripts/launcher.py already fully configured or could not find hooks");
                    }
                } else {
                    results.push("❌ scripts/launcher.py not found");
                }
                
                // 2. Wire dashboard/app/config.py
                const configPath = path.join(projectRoot, "dashboard/app/config.py");
                if (fs.existsSync(configPath)) {
                    let content = fs.readFileSync(configPath, "utf-8");
                    let modified = false;
                    
                    // Insert into LEAGUE_CONFIGS
                    if (!content.includes(`"${args.leagueKey}":`)) {
                        const marker = "LEAGUE_CONFIGS: dict[str, dict] = {";
                        const idx = content.indexOf(marker);
                        if (idx !== -1) {
                            const configEntry = `\n    "${args.leagueKey}": {\n        "league": "${args.leagueCode}",\n        "model_dir": "${args.modelDir}",\n        "feature_store_dir": "${args.featureStoreDir}",\n    },`;
                            content = content.slice(0, idx + marker.length) + configEntry + content.slice(idx + marker.length);
                            modified = true;
                        }
                    }
                    
                    // Insert into _URL_LEAGUE_PATTERNS
                    if (!content.includes(`"${args.leagueKey}"`) && args.urlPatterns.length > 0) {
                        const marker = "_URL_LEAGUE_PATTERNS: list[tuple[str, str]] = [";
                        const idx = content.indexOf(marker);
                        if (idx !== -1) {
                            const patternEntries = args.urlPatterns.map(p => `\n    (r"${p}", "${args.leagueKey}"),`).join("");
                            content = content.slice(0, idx + marker.length) + patternEntries + content.slice(idx + marker.length);
                            modified = true;
                        }
                    }
                    
                    if (modified) {
                        fs.writeFileSync(configPath, content, "utf-8");
                        results.push("✅ Successfully updated dashboard/app/config.py presets");
                    } else {
                        results.push("ℹ️ dashboard/app/config.py already configured or hooks missing");
                    }
                } else {
                    results.push("❌ dashboard/app/config.py not found");
                }
                
                // 3. Wire src/bbl_pipeline/app/live_streamlit_app.py
                const streamlitPath = path.join(projectRoot, "src/bbl_pipeline/app/live_streamlit_app.py");
                if (fs.existsSync(streamlitPath)) {
                    let content = fs.readFileSync(streamlitPath, "utf-8");
                    let modified = false;
                    
                    // JSON Sources list
                    if (!content.includes(`"${args.leagueKey} ML+MC`)) {
                        const marker = "JSON_SOURCES = {";
                        const idx = content.indexOf(marker);
                        if (idx !== -1) {
                            const entries = `\n    "${args.leagueKey} ML+MC (${args.leagueCode}_live_ml.json)": "data/${args.leagueCode}_live_ml.json",\n    "${args.leagueKey} ML+MC (${args.leagueCode}_live_ml_1.json)": "data/${args.leagueCode}_live_ml_1.json",\n    "${args.leagueKey} MC-only (${args.leagueCode}_live_mc.json)": "data/${args.leagueCode}_live_mc.json",\n    "${args.leagueKey} MC-only (${args.leagueCode}_live_mc_1.json)": "data/${args.leagueCode}_live_mc_1.json",`;
                            content = content.slice(0, idx + marker.length) + entries + content.slice(idx + marker.length);
                            modified = true;
                        }
                    }
                    
                    // PREDICTOR_CONFIGS
                    if (!content.includes(`"${args.leagueKey} ML+MC"`)) {
                        const marker = "PREDICTOR_CONFIGS = {";
                        const idx = content.indexOf(marker);
                        if (idx !== -1) {
                            const configEntry = `\n    "${args.leagueKey} ML+MC": {\n        "output_json": "data/${args.leagueCode}_live_ml.json",\n        "mc_only": false,\n        "model_dir": "${args.modelDir}",\n        "feature_store_dir": "${args.featureStoreDir}",\n        "league": "${args.leagueCode}",\n        "states_dir": "data/match_states/${args.leagueCode}",\n    },\n    "${args.leagueKey} MC-only": {\n        "output_json": "data/${args.leagueCode}_live_mc.json",\n        "mc_only": true,\n        "model_dir": "${args.modelDir}",\n        "feature_store_dir": "${args.featureStoreDir}",\n        "league": "${args.leagueCode}",\n        "states_dir": "data/match_states/${args.leagueCode}",\n    },`;
                            content = content.slice(0, idx + marker.length) + configEntry + content.slice(idx + marker.length);
                            modified = true;
                        }
                    }
                    
                    // is_league flag detection in decision probabilities section
                    if (!content.includes(`is_${args.leagueCode} =`)) {
                        const marker = "batting_team = d.get(\"batting_team\", \"\")";
                        const idx = content.indexOf(marker);
                        if (idx !== -1) {
                            // Ensure general variables like league_code, model_dir_lower exist or append them
                            let addition = "";
                            if (!content.includes("league_code = (d.get(\"league\") or \"\").lower()")) {
                                addition += `\n    league_code = (d.get("league") or "").lower()\n    model_dir_lower = (d.get("model_dir") or "").lower()`;
                            }
                            addition += `\n    is_${args.leagueCode} = league_code == "${args.leagueCode}" or "${args.modelDir}" in model_dir_lower`;
                            content = content.slice(0, idx + marker.length) + addition + content.slice(idx + marker.length);
                            modified = true;
                        }
                    }
                    
                    // league_name formatting map
                    if (!content.includes(`is_${args.leagueCode} else`)) {
                        const marker = 'league_name = "🏏 ';
                        const idx = content.indexOf(marker);
                        if (idx !== -1) {
                            const match_block = `league_name = "🏏 ${args.leagueKey}" if is_${args.leagueCode} else ("🏏 `;
                            content = content.replace('league_name = "🏏 ', match_block);
                            modified = true;
                        }
                    }
                    
                    if (modified) {
                        fs.writeFileSync(streamlitPath, content, "utf-8");
                        results.push("✅ Successfully updated live_streamlit_app.py runtime and presets");
                    } else {
                        results.push("ℹ️ live_streamlit_app.py already configured or hooks missing");
                    }
                } else {
                    results.push("❌ live_streamlit_app.py not found");
                }
                
                return `### 🚀 Wiring Operation Complete\n\n` + results.join("\n");
            }
        }
    ],
});

