import * as vscode from 'vscode';
import * as cp from 'child_process';
import * as path from 'path';

interface MatchState {
    batting: string;
    bowling: string;
    score: number;
    wickets: number;
    overs: number;
    target?: number;
}

export function activate(context: vscode.ExtensionContext) {

    const handler: vscode.ChatRequestHandler = async (request: vscode.ChatRequest, context: vscode.ChatContext, stream: vscode.ChatResponseStream, token: vscode.CancellationToken) => {
        
        stream.progress('Analyzing commentary...');

        try {
            // 1. Use LM to parse the natural language into structured data
            const [model] = await vscode.lm.selectChatModels({ family: 'gpt-4o' });
            
            if (!model) {
                stream.markdown('Error: No supported LLM found to parse the request.');
                return;
            }

            const systemPrompt = `
                You are a cricket match data parser. 
                Extract the following fields from the user's commentary:
                - batting (Team name)
                - bowling (Team name)
                - score (Current runs)
                - wickets (Current wickets lost)
                - overs (Overs bowled, e.g. 12.4)
                - target (Target score if chasing, else null)
                
                Return ONLY a JSON object. Example:
                { "batting": "India", "bowling": "South Africa", "score": 120, "wickets": 2, "overs": 12.4, "target": null }
            `;

            const messages = [
                vscode.LanguageModelChatMessage.User(systemPrompt),
                vscode.LanguageModelChatMessage.User(request.prompt)
            ];

            const chatResponse = await model.sendRequest(messages, {}, token);
            let jsonStr = '';
            for await (const fragment of chatResponse.text) {
                jsonStr += fragment;
            }

            // Clean json string (remove markdown code blocks if any)
            jsonStr = jsonStr.replace(/```json/g, '').replace(/```/g, '').trim();
            
            let state: MatchState;
            try {
                state = JSON.parse(jsonStr);
            } catch (e) {
                stream.markdown(`Failed to parse match state from commentary. Raw LM output: ${jsonStr}`);
                return;
            }

            stream.progress(`Running prediction for ${state.batting} vs ${state.bowling}...`);

            // 2. Call the Python script
            const workspaceFolders = vscode.workspace.workspaceFolders;
            if (!workspaceFolders) {
                stream.markdown('No workspace open.');
                return;
            }
            
            const rootPath = workspaceFolders[0].uri.fsPath;
            const scriptPath = path.join(rootPath, 'scripts', 'quick_predict.py');
            
            const args = [
                scriptPath,
                '--batting', `"${state.batting}"`,
                '--bowling', `"${state.bowling}"`,
                '--score', state.score.toString(),
                '--wickets', state.wickets.toString(),
                '--overs', state.overs.toString()
            ];

            if (state.target) {
                args.push('--target', state.target.toString());
            }

            // Execute Python
            const pythonCommand = `python ${args.join(' ')}`;
            
            // We use exec instead of spawn to easily capture all output
            await new Promise<void>((resolve, reject) => {
                cp.exec(pythonCommand, { cwd: rootPath }, (err, stdout, stderr) => {
                    if (err) {
                        stream.markdown(`Error running prediction script:\n\`\`\`\n${stderr}\n\`\`\``);
                        resolve();
                        return;
                    }

                    // Parse output
                    // Expected output format from quick_predict.py:
                    // WIN_PROBABILITY:0.8562
                    // PROJECTED:197
                    // RESOURCE_PROB:0.6269

                    const winProbMatch = stdout.match(/WIN_PROBABILITY:([\d\.]+)/);
                    const projectedMatch = stdout.match(/PROJECTED:(\d+)/);
                    const resourceProbMatch = stdout.match(/RESOURCE_PROB:([\d\.]+)/);

                    if (winProbMatch && projectedMatch) {
                        const winProb = parseFloat(winProbMatch[1]);
                        const projected = parseInt(projectedMatch[1]);
                        const resourceProb = resourceProbMatch ? parseFloat(resourceProbMatch[1]) : 0;

                        stream.markdown(`### Match Prediction\n\n`);
                        stream.markdown(`**${state.batting}** vs **${state.bowling}**\n`);
                        stream.markdown(`State: ${state.score}/${state.wickets} (${state.overs} ov)\n\n`);
                        
                        stream.markdown(`| Metric | Value |\n`);
                        stream.markdown(`| :--- | :--- |\n`);
                        stream.markdown(`| **Win Probability** | **${(winProb * 100).toFixed(1)}%** |\n`);
                        stream.markdown(`| **Projected Score** | **${projected}** |\n`);
                        stream.markdown(`| Resource Win Prob | ${(resourceProb * 100).toFixed(1)}% |\n`);
                        
                        if (state.target) {
                            const req = state.target - state.score;
                            stream.markdown(`\n*Chasing ${state.target}. Need ${req} runs.*`);
                        }
                    } else {
                        stream.markdown(`Could not parse script output:\n\`\`\`\n${stdout}\n\`\`\``);
                    }
                    resolve();
                });
            });

        } catch (err) {
            if (err instanceof Error) {
                stream.markdown(`Error: ${err.message}`);
            }
        }
    };

    const cricket = vscode.chat.createChatParticipant('cricket.predict', handler);
    cricket.iconPath = new vscode.ThemeIcon('graph');
    context.subscriptions.push(cricket);
}

export function deactivate() {}
