#!/usr/bin/env node
// Headless browser simulation: every user in expected.json goes through the real
// website at the same time (sign-up, email verification, login, upload, waiting
// on the job page, encrypted download). Timings and API calls go to results.json;
// tests/e2e/analyze.py turns them into the report. Started by run.sh.
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright-core');

const BASE = process.env.BASE_URL || 'https://localhost:18443';
const MAILHOG = process.env.MAILHOG_URL || 'http://127.0.0.1:18125';
const DATA = process.env.DATA_DIR;
const OUT = process.env.OUT_DIR;
const PASSWORD = 'SimPassw0rd-2026';
const ZIP_PASSWORD = 'zip-Passw0rd-sim';
const JOB_TIMEOUT_MS = 40 * 60 * 1000;
const DOWNLOAD_TIMEOUT_MS = 10 * 60 * 1000;
const MAX_DOWNLOAD_ATTEMPTS = 20;

const expected = JSON.parse(fs.readFileSync(path.join(DATA, 'expected.json')));
const t0 = Date.now();
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const log = (user, msg) =>
	console.log(`[+${((Date.now() - t0) / 1000).toFixed(1).padStart(7)}s] ${user.padEnd(6)} ${msg}`);

function deferred() {
	let resolve;
	const promise = new Promise((r) => (resolve = r));
	return { promise, resolve };
}

function decodePart(part) {
	const headers = part.Headers || {};
	const cte = ((headers['Content-Transfer-Encoding'] || [''])[0] || '').toLowerCase();
	let body = part.Body || '';
	if (cte === 'base64') return Buffer.from(body, 'base64').toString();
	if (cte === 'quoted-printable') {
		body = body.replace(/=\r?\n/g, '');
		return Buffer.from(body.replace(/=([0-9A-Fa-f]{2})/g, (_, h) => String.fromCharCode(parseInt(h, 16))), 'latin1').toString();
	}
	return body;
}

async function waitForVerifyUrl(email, timeoutMs = 120000) {
	const deadline = Date.now() + timeoutMs;
	while (Date.now() < deadline) {
		const res = await fetch(`${MAILHOG}/api/v2/search?kind=to&query=${encodeURIComponent(email)}`);
		const { items = [] } = await res.json();
		for (const item of items) {
			const subject = (item.Content.Headers.Subject || [''])[0];
			if (!subject.includes('verify your email')) continue;
			const parts = (item.MIME && item.MIME.Parts) || [item.Content];
			for (const part of parts) {
				const m = decodePart(part).match(/https?:\/\/[^\s"'<>]*\/verify\?token=[^\s"'<>]*/);
				if (m) return m[0];
			}
		}
		await sleep(500);
	}
	throw new Error(`no verification email for ${email} within ${timeoutMs / 1000}s`);
}

const apiPath = (url) =>
	new URL(url).pathname.replace(/[0-9a-f]{8}-[0-9a-f-]{27}/g, '{id}');

function instrument(page, rec) {
	page.on('console', (m) => {
		if (m.type() === 'error') rec.consoleErrors.push(m.text().slice(0, 300));
	});
	page.on('pageerror', (e) => rec.pageErrors.push(String(e).slice(0, 300)));
	page.on('requestfailed', (r) => {
		const failure = r.failure() ? r.failure().errorText : '';
		// Leaving a page cancels its polls; those aren't failures.
		if (r.url().startsWith(BASE) && failure !== 'net::ERR_ABORTED')
			rec.failedRequests.push({ url: new URL(r.url()).pathname, failure });
	});
	// requestfinished, not response: responseEnd is only known once the body has arrived.
	page.on('requestfinished', async (req) => {
		const url = req.url();
		if (!url.startsWith(BASE + '/api/')) return;
		const res = await req.response().catch(() => null);
		if (!res) return;
		const timing = req.timing();
		const call = {
			t: (Date.now() - t0) / 1000,
			method: req.method(),
			path: apiPath(url),
			status: res.status(),
			ms: timing.responseEnd > 0 ? timing.responseEnd : null
		};
		rec.apiCalls.push(call);
		if (call.method === 'GET' && call.path === '/api/jobs/{id}' && res.ok()) {
			try {
				const job = await res.json();
				const key = job.status;
				if (!(key in rec.statusFirstSeen)) rec.statusFirstSeen[key] = call.t;
				if (job.queue_position != null) rec.queuePositionsSeen.push(job.queue_position);
			} catch {
				/* the page navigated away before the body arrived */
			}
		}
	});
}

async function waitForCaptcha(page) {
	// The widget fills a hidden input once the token is issued. Backend ignores
	// it here, but the page refuses to submit without one.
	await page.waitForFunction(
		() => {
			const el = document.querySelector('[name="cf-turnstile-response"]');
			return el && el.value;
		},
		null,
		{ timeout: 90000 }
	);
}

async function runUser(name, cfg, ctx, shared) {
	const email = `${name}@example.org`;
	const rec = {
		name,
		email,
		format: cfg.format,
		selection: cfg.selection,
		expectedOutcome: cfg.outcome,
		steps: [],
		findings: [],
		apiCalls: [],
		consoleErrors: [],
		pageErrors: [],
		failedRequests: [],
		statusFirstSeen: {},
		queuePositionsSeen: [],
		downloadAttempts: [],
		ok: true
	};
	shared.records[name] = rec;
	const page = await ctx.newPage();
	instrument(page, rec);

	const step = async (label, fn) => {
		const start = Date.now();
		try {
			const value = await fn();
			rec.steps.push({ label, startS: (start - t0) / 1000, seconds: (Date.now() - start) / 1000, ok: true });
			log(name, `${label} ok (${((Date.now() - start) / 1000).toFixed(1)}s)`);
			return value;
		} catch (e) {
			rec.steps.push({ label, startS: (start - t0) / 1000, seconds: (Date.now() - start) / 1000, ok: false, error: String(e).slice(0, 500) });
			rec.ok = false;
			log(name, `${label} FAILED: ${String(e).split('\n')[0]}`);
			await page.screenshot({ path: path.join(OUT, 'screens', `${name}-FAILED-${label}.png`), fullPage: true }).catch(() => {});
			throw e;
		}
	};

	const files = cfg.files.map((f) => path.join(DATA, f));
	const byExt = (ext) => files.find((f) => f.endsWith(ext));

	try {
		await step('home', async () => {
			await page.goto(BASE + '/', { waitUntil: 'networkidle' });
			const text = await page.locator('.grid .card').first().innerText();
			rec.homeMentionsPlink = text.includes('PLINK');
			await page.locator('a[href="/signup"]').first().click();
			await page.waitForURL('**/signup');
		});

		await step('signup', async () => {
			await page.fill('#email', email);
			await page.fill('#password', PASSWORD);
			await page.check('input[type=checkbox]');
			await waitForCaptcha(page);
			await page.click('button[type=submit]');
			await page.locator('.card strong', { hasText: email }).waitFor({ timeout: 60000 });
		});

		const verifyUrl = await step('email-arrives', () => waitForVerifyUrl(email));

		await step('verify', async () => {
			await page.goto(verifyUrl);
			await page.locator('.form-wrap a[href="/login"]').waitFor({ timeout: 60000 });
			await page.locator('.form-wrap a[href="/login"]').click();
			await page.waitForURL('**/login');
		});

		await step('login', async () => {
			await page.fill('#email', email);
			await page.fill('#password', PASSWORD);
			await waitForCaptcha(page);
			await page.click('button[type=submit]');
			await page.waitForURL('**/dashboard', { timeout: 60000 });
		});

		const submitAndWait = async () => {
			await page.check('form input[type=checkbox]');
			await page.click('button[type=submit]');
		};
		const uploadPicker = 'input[type=file][multiple]';

		await step('open-upload', async () => {
			await page.locator('a[href="/upload"]').first().click();
			await page.waitForURL('**/upload');
			await page.locator(uploadPicker).waitFor({ state: 'attached' });
		});

		await step('upload', async () => {
			if (cfg.selection === 'together' || cfg.selection === 'dropped') {
				if (cfg.selection === 'together') {
					await page.setInputFiles(uploadPicker, [byExt('.bed'), byExt('.bim'), byExt('.fam')]);
				} else {
					// A real drop event carrying all three files onto the drop zone.
					const payload = [byExt('.bed'), byExt('.bim'), byExt('.fam')].map((f) => ({
						name: path.basename(f),
						b64: fs.readFileSync(f).toString('base64')
					}));
					const dataTransfer = await page.evaluateHandle((items) => {
						const dt = new DataTransfer();
						for (const item of items) {
							const bytes = Uint8Array.from(atob(item.b64), (c) => c.charCodeAt(0));
							dt.items.add(new File([bytes], item.name));
						}
						return dt;
					}, payload);
					await page.dispatchEvent('.dropzone', 'drop', { dataTransfer });
				}
				await submitAndWait();
				// Nothing was sent if the browser's form validation stopped the submit.
				const moved = await page.waitForURL('**/jobs/*', { timeout: 8000 }).then(() => true, () => false);
				if (!moved) {
					const blocked = await page.evaluate(() => {
						const bim = document.querySelector('#bim');
						const fam = document.querySelector('#fam');
						return {
							bimEmpty: !!bim && !bim.validity.valid,
							famEmpty: !!fam && !fam.validity.valid,
							banner: document.querySelector('.error-banner')?.innerText || null
						};
					});
					rec.findings.push({ kind: 'plink-together-blocked', ...blocked });
					log(name, `selecting .bed/.bim/.fam together did not submit: ${JSON.stringify(blocked)}; picking .bim and .fam again`);
					await page.setInputFiles('#bim', byExt('.bim'));
					await page.setInputFiles('#fam', byExt('.fam'));
					await page.click('button[type=submit]');
				}
			} else if (cfg.format === 'plink' || cfg.format === 'low_overlap') {
				await page.setInputFiles(uploadPicker, byExt('.bed'));
				if (name === 'user5') {
					// Submitting without .bim/.fam must explain itself on the page.
					await submitAndWait();
					const banner = await page.locator('.error-banner').innerText({ timeout: 8000 }).catch(() => null);
					rec.findings.push({ kind: 'bed-only', banner });
				}
				await page.setInputFiles('#bim', byExt('.bim'));
				await page.setInputFiles('#fam', byExt('.fam'));
				await submitAndWait();
			} else if (cfg.format === 'bgen') {
				await page.setInputFiles(uploadPicker, byExt('.bgen'));
				await page.setInputFiles('#sample', byExt('.sample'));
				await submitAndWait();
			} else {
				await page.setInputFiles(uploadPicker, files[0]);
				await submitAndWait();
			}
			await page.waitForURL('**/jobs/*', { timeout: 300000 });
		});
		rec.jobId = page.url().split('/jobs/')[1];
		shared.jobIds[name] = rec.jobId;
		rec.uploadDoneS = (Date.now() - t0) / 1000;

		if (name === 'user7') {
			// One active job per user: a second upload must be refused, with a message.
			await step('second-upload-refused', async () => {
				const second = await ctx.newPage();
				instrument(second, rec);
				await second.goto(BASE + '/upload');
				await second.setInputFiles(uploadPicker, byExt('.bed'));
				await second.setInputFiles('#bim', byExt('.bim'));
				await second.setInputFiles('#fam', byExt('.fam'));
				await second.check('form input[type=checkbox]');
				const [resp] = await Promise.all([
					second.waitForResponse((r) => r.url().endsWith('/api/uploads')),
					second.click('button[type=submit]')
				]);
				const banner = await second.locator('.error-banner').innerText({ timeout: 15000 });
				rec.findings.push({ kind: 'second-upload', status: resp.status(), banner });
				await second.close();
				if (resp.status() !== 409) throw new Error(`expected 409, got ${resp.status()}`);
			});
		}

		const outcome = await step('wait-for-job', async () => {
			const form = page.locator('input[type=password]').first();
			const failed = page.locator('.card .error-banner');
			const pageError = page.locator('body > * .error-banner');
			const deadline = Date.now() + JOB_TIMEOUT_MS;
			while (Date.now() < deadline) {
				if (await form.count()) return 'done';
				if (await failed.count()) return 'failed';
				if (await pageError.count()) throw new Error(`job page error: ${await pageError.first().innerText()}`);
				await sleep(1000);
			}
			throw new Error('job did not finish in time');
		});
		rec.outcome = outcome;
		rec.jobFinishedS = (Date.now() - t0) / 1000;
		await page.screenshot({ path: path.join(OUT, 'screens', `${name}-job-${outcome}.png`), fullPage: true });

		if (outcome === 'failed') {
			rec.errorMessage = await page.locator('.card .error-banner').innerText();
			log(name, `job failed: ${rec.errorMessage.slice(0, 120)}`);
		}
		if (outcome !== cfg.outcome) {
			rec.ok = false;
			throw new Error(`expected job outcome ${cfg.outcome}, got ${outcome}`);
		}
	} catch (e) {
		rec.fatal = String(e).slice(0, 500);
	} finally {
		shared.reachedBarrier(name);
	}

	// Every finished user downloads at the same moment, to hit the 9-at-once cap.
	await shared.barrier;

	try {
		if (rec.outcome === 'done') {
			await step('download', async () => {
				await page.fill('input[type=password] >> nth=0', ZIP_PASSWORD);
				await page.fill('input[type=password] >> nth=1', ZIP_PASSWORD);
				for (let attempt = 1; attempt <= MAX_DOWNLOAD_ATTEMPTS; attempt++) {
					const start = Date.now();
					const downloadP = page.waitForEvent('download', { timeout: DOWNLOAD_TIMEOUT_MS });
					const responseP = page.waitForResponse((r) => r.url().endsWith('/download'), { timeout: DOWNLOAD_TIMEOUT_MS });
					await page.click('button[type=submit]');
					const res = await responseP;
					if (res.ok()) {
						const download = await downloadP;
						const dest = path.join(OUT, 'zips', `${name}.zip`);
						await download.saveAs(dest);
						rec.downloadAttempts.push({ attempt, status: res.status(), seconds: (Date.now() - start) / 1000 });
						rec.zipBytes = fs.statSync(dest).size;
						return;
					}
					downloadP.catch(() => {});
					const banner = await page.locator('form .error-banner').innerText({ timeout: 15000 }).catch(() => null);
					rec.downloadAttempts.push({ attempt, status: res.status(), seconds: (Date.now() - start) / 1000, banner });
					log(name, `download attempt ${attempt}: ${res.status()}`);
					if (res.status() !== 429) throw new Error(`download failed with ${res.status()}: ${banner}`);
					await sleep(5000);
				}
				throw new Error('download never got a slot');
			});
		}

		await step('dashboard', async () => {
			await page.goto(BASE + '/dashboard', { waitUntil: 'networkidle' });
			rec.dashboardRows = await page.locator('table tbody tr').count();
			if (rec.dashboardRows !== 1) throw new Error(`expected 1 job on the dashboard, saw ${rec.dashboardRows}`);
			await page.screenshot({ path: path.join(OUT, 'screens', `${name}-dashboard.png`), fullPage: true });
		});

		if (name === 'user1' && shared.jobIds.user2) {
			await step('other-users-job-refused', async () => {
				const [resp] = await Promise.all([
					page.waitForResponse((r) => r.url().includes(`/api/jobs/${shared.jobIds.user2}`)),
					page.goto(`${BASE}/jobs/${shared.jobIds.user2}`)
				]);
				const banner = await page.locator('.error-banner').first().innerText({ timeout: 15000 });
				rec.findings.push({ kind: 'other-users-job', status: resp.status(), banner });
				if (resp.status() !== 404) throw new Error(`expected 404, got ${resp.status()}`);
			});
		}
	} catch (e) {
		rec.fatal = rec.fatal || String(e).slice(0, 500);
	}
	await page.close().catch(() => {});
}

(async () => {
	fs.mkdirSync(path.join(OUT, 'screens'), { recursive: true });
	fs.mkdirSync(path.join(OUT, 'zips'), { recursive: true });
	// SIM_USERS=user1 runs a subset, e.g. one job alone as a contention baseline.
	const only = process.env.SIM_USERS ? process.env.SIM_USERS.split(',') : null;
	const names = Object.keys(expected).filter((n) => !only || only.includes(n));
	const browser = await chromium.launch({ headless: true });
	log('sim', `${names.length} users, chromium ${browser.version()}`);

	const barrier = deferred();
	const pending = new Set(names);
	const shared = {
		records: {},
		jobIds: {},
		barrier: barrier.promise,
		reachedBarrier(name) {
			pending.delete(name);
			if (pending.size === 0) {
				log('sim', 'all jobs finished; everyone downloads now');
				shared.downloadsStartS = (Date.now() - t0) / 1000;
				barrier.resolve();
			}
		}
	};

	await Promise.all(
		names.map(async (name) => {
			// Two users have a French browser; the site picks its language from it.
			const ctx = await browser.newContext({
				ignoreHTTPSErrors: true,
				acceptDownloads: true,
				locale: name === 'user3' || name === 'user9' ? 'fr-CA' : 'en-CA'
			});
			try {
				await runUser(name, expected[name], ctx, shared);
			} finally {
				await ctx.close();
			}
		})
	);
	await browser.close();

	const result = {
		base: BASE,
		totalSeconds: (Date.now() - t0) / 1000,
		downloadsStartS: shared.downloadsStartS,
		jobIds: shared.jobIds,
		zipPassword: ZIP_PASSWORD,
		users: shared.records
	};
	fs.writeFileSync(path.join(OUT, 'results.json'), JSON.stringify(result, null, 1));
	const failed = Object.values(shared.records).filter((r) => !r.ok);
	log('sim', `finished in ${result.totalSeconds.toFixed(0)}s, ${failed.length} user(s) with failures`);
	process.exit(failed.length ? 1 : 0);
})().catch((e) => {
	console.error(e);
	process.exit(2);
});
