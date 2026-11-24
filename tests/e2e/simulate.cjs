#!/usr/bin/env node
// Headless browser simulation: every user in expected.json goes through the real
// website at the same time (sign-up, email verification, login, upload, waiting
// on the job page, encrypted download), some of them for several jobs in a row
// (JOBS_PER_USER). Timings and API calls go to results.json;
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
const JOB_TIMEOUT_MS = 60 * 60 * 1000;
// Users that submit again as soon as their previous job ends (default 1 job).
// user12's uploads are rejected each time: a failed job mustn't block the next.
const JOBS_PER_USER = { user1: 3, user4: 2, user8: 2, user11: 2, user12: 2 };
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
		jobsPlanned: JOBS_PER_USER[name] || 1,
		jobs: [],
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

	// The session cookie lasts 30 min from login and isn't renewed, so a user
	// waiting on a long job gets logged out. They log in again, as a person
	// would; each time is recorded as a finding.
	const relogin = async (where) => {
		rec.findings.push({ kind: 'session-expired', t: (Date.now() - t0) / 1000, where });
		log(name, `logged out (${where}); logging in again`);
		await page.goto(BASE + '/login', { waitUntil: 'networkidle' });
		await page.fill('#email', email);
		await page.fill('#password', PASSWORD);
		await waitForCaptcha(page);
		await page.click('button[type=submit]');
		await page.waitForURL('**/dashboard', { timeout: 60000 });
	};
	const loggedOut = async () =>
		page.url().includes('/login') ||
		(await page.locator('.error-banner', { hasText: 'Not authenticated' }).count()) > 0;
	// Opens url, logging in again first if the session has expired.
	const openWithSession = async (url, where) => {
		await page.goto(url, { waitUntil: 'networkidle' });
		if (await loggedOut()) {
			await relogin(where);
			await page.goto(url, { waitUntil: 'networkidle' });
		}
	};

	// Encrypted download of the job open on the page; retries while the
	// 9-at-once download cap answers 429.
	const download = async (job) => {
		await page.fill('input[type=password] >> nth=0', ZIP_PASSWORD);
		await page.fill('input[type=password] >> nth=1', ZIP_PASSWORD);
		for (let attempt = 1; attempt <= MAX_DOWNLOAD_ATTEMPTS; attempt++) {
			const start = Date.now();
			const downloadP = page.waitForEvent('download', { timeout: DOWNLOAD_TIMEOUT_MS });
			const responseP = page.waitForResponse((r) => r.url().endsWith('/download'), { timeout: DOWNLOAD_TIMEOUT_MS });
			await page.click('button[type=submit]');
			const res = await responseP;
			if (res.ok()) {
				const dl = await downloadP;
				const dest = path.join(OUT, 'zips', `${name}-job${job.k}.zip`);
				await dl.saveAs(dest);
				job.downloadAttempts.push({ attempt, status: res.status(), seconds: (Date.now() - start) / 1000 });
				job.zipBytes = fs.statSync(dest).size;
				return;
			}
			downloadP.catch(() => {});
			const banner = await page.locator('form .error-banner').innerText({ timeout: 15000 }).catch(() => null);
			job.downloadAttempts.push({ attempt, status: res.status(), seconds: (Date.now() - start) / 1000, banner });
			log(name, `job ${job.k} download attempt ${attempt}: ${res.status()}`);
			if (res.status() === 401) {
				const jobUrl = page.url();
				await relogin('download');
				await page.goto(jobUrl, { waitUntil: 'networkidle' });
				await page.fill('input[type=password] >> nth=0', ZIP_PASSWORD);
				await page.fill('input[type=password] >> nth=1', ZIP_PASSWORD);
				continue;
			}
			if (res.status() !== 429) throw new Error(`download failed with ${res.status()}: ${banner}`);
			await sleep(5000);
		}
		throw new Error('download never got a slot');
	};

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

		// One upload through the form, the same way each time for this user.
		const uploadOnce = async (k) => {
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
				if (name === 'user5' && k === 1) {
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
		};

		const waitForJob = async () => {
			const form = page.locator('input[type=password]').first();
			const failed = page.locator('.card .error-banner');
			// Only a banner outside the job card means the page itself failed to load.
			// Checking both selectors one after the other can otherwise race a job
			// that fails between the two checks.
			const pageError = page.locator('.error-banner:not(.card .error-banner)');
			const deadline = Date.now() + JOB_TIMEOUT_MS;
			while (Date.now() < deadline) {
				if (await form.count()) return 'done';
				if (await failed.count()) return 'failed';
				if (await pageError.count()) {
					const text = await pageError.first().innerText();
					if (!text.includes('Not authenticated')) throw new Error(`job page error: ${text}`);
					const jobUrl = page.url();
					await relogin('job page');
					await page.goto(jobUrl, { waitUntil: 'networkidle' });
				}
				await sleep(1000);
			}
			throw new Error('job did not finish in time');
		};

		// Jobs one after the other: the next upload goes in as soon as the previous
		// job ends (one active job per user), so later uploads join the queue while
		// other users' jobs are still waiting.
		for (let k = 1; k <= rec.jobsPlanned; k++) {
			const job = { k, downloadAttempts: [] };
			rec.jobs.push(job);

			await step(`job${k}-open-upload`, async () => {
				if (k === 1) {
					await page.locator('a[href="/upload"]').first().click();
					await page.waitForURL('**/upload');
				} else {
					await openWithSession(BASE + '/upload', 'upload page');
				}
				await page.locator(uploadPicker).waitFor({ state: 'attached' });
			});

			await step(`job${k}-upload`, () => uploadOnce(k));
			job.jobId = page.url().split('/jobs/')[1];
			job.uploadDoneS = (Date.now() - t0) / 1000;
			shared.jobIds[name] = job.jobId;
			rec.jobId = job.jobId;
			rec.uploadDoneS = rec.uploadDoneS || job.uploadDoneS;

			if (name === 'user7' && k === 1) {
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

			job.outcome = await step(`job${k}-wait`, waitForJob);
			job.finishedS = (Date.now() - t0) / 1000;
			rec.outcome = job.outcome;
			rec.jobFinishedS = job.finishedS;
			await page.screenshot({ path: path.join(OUT, 'screens', `${name}-job${k}-${job.outcome}.png`), fullPage: true });
			if (job.outcome === 'failed') {
				job.errorMessage = await page.locator('.card .error-banner').innerText();
				rec.errorMessage = job.errorMessage;
				log(name, `job ${k} failed: ${job.errorMessage.slice(0, 120)}`);
			}
			if (job.outcome !== cfg.outcome) {
				rec.ok = false;
				throw new Error(`expected job ${k} outcome ${cfg.outcome}, got ${job.outcome}`);
			}
			// Earlier jobs are downloaded straight away; the last one waits for
			// everyone, so all downloads hit the 9-at-once cap together.
			if (k < rec.jobsPlanned && job.outcome === 'done') await step(`job${k}-download`, () => download(job));
		}
	} catch (e) {
		rec.fatal = String(e).slice(0, 500);
	} finally {
		shared.reachedBarrier(name);
	}

	await shared.barrier;

	try {
		const last = rec.jobs[rec.jobs.length - 1];
		if (last && last.outcome === 'done' && rec.jobs.length === rec.jobsPlanned) {
			await step(`job${last.k}-download`, () => download(last));
		}

		await step('dashboard', async () => {
			await openWithSession(BASE + '/dashboard', 'dashboard');
			rec.dashboardRows = await page.locator('table tbody tr').count();
			if (rec.dashboardRows !== rec.jobsPlanned)
				throw new Error(`expected ${rec.jobsPlanned} job(s) on the dashboard, saw ${rec.dashboardRows}`);
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
		jobsPerUser: JOBS_PER_USER,
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
