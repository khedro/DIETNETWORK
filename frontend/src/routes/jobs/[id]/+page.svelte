<script lang="ts">
	import { page } from '$app/stores';
	import { onMount, onDestroy } from 'svelte';
	import { api, type JobDetail, ApiError } from '$lib/api';
	import StatusBadge from '$lib/components/StatusBadge.svelte';

	let job: JobDetail | null = null;
	let error = '';
	let interval: ReturnType<typeof setInterval>;

	async function refresh() {
		try {
			job = await api.getJob($page.params.id);
			error = '';
			if (job.status === 'done' || job.status === 'failed') clearInterval(interval);
		} catch (e) {
			error = e instanceof ApiError ? e.message : 'Could not load this job.';
			clearInterval(interval);
		}
	}

	onMount(() => {
		refresh();
		interval = setInterval(refresh, 4000);
	});
	onDestroy(() => clearInterval(interval));

	$: modelColumns = job?.predictions?.rows?.length
		? Object.keys(job.predictions.rows[0]).filter((k) => k !== 'samples')
		: [];
</script>

<a href="/dashboard" class="muted">&larr; Back to dashboard</a>

{#if error}
	<div class="error-banner" style="margin-top:1rem">{error}</div>
{:else if !job}
	<p class="muted">Loading…</p>
{:else}
	<div class="header-row">
		<h1>Analysis <code>{job.id.slice(0, 8)}</code></h1>
		<StatusBadge status={job.status} />
	</div>

	{#if job.status === 'queued' || job.status === 'running'}
		<div class="card">
			<p>
				Your job is {job.status === 'queued' ? 'queued and will start shortly' : 'running'}. The
				Diet Network ensemble runs 15 models sequentially, so this can take a few minutes. This
				page updates automatically.
			</p>
		</div>
	{:else if job.status === 'failed'}
		<div class="card">
			<p class="error-banner">{job.error_message ?? 'The job failed.'}</p>
			<p class="muted">
				This is usually caused by malformed input or a genome build mismatch. You can start a new
				analysis from the dashboard.
			</p>
		</div>
	{:else if job.status === 'done'}
		<div class="stack">
			{#if job.is_reliable === false}
				<div class="warn-banner">
					⚠️ <strong>Low SNP overlap ({job.snp_overlap_count} / {job.snp_overlap_total}).</strong>
					Diet Network's authors recommend discarding predictions when overlap with the reference
					SNP panel is under 1000 SNPs. Treat these results as unreliable — a common cause is a
					genome build other than GRCh38.
				</div>
			{:else}
				<div class="card">
					SNP overlap with Diet Network reference panel: <strong
						>{job.snp_overlap_count} / {job.snp_overlap_total}</strong
					> ✅
				</div>
			{/if}

			<div class="card" style="padding:0; overflow-x:auto;">
				<table>
					<thead>
						<tr>
							<th>Sample</th>
							{#each modelColumns as col}<th>{col}</th>{/each}
						</tr>
					</thead>
					<tbody>
						{#each job.predictions?.rows ?? [] as row}
							<tr>
								<td>{row['samples']}</td>
								{#each modelColumns as col}<td>{row[col]}</td>{/each}
							</tr>
						{/each}
					</tbody>
				</table>
			</div>

			<a class="btn btn-secondary" href={api.downloadUrl(job.id)} target="_blank" rel="noreferrer">
				Download predictions (.txt)
			</a>
		</div>
	{/if}
{/if}

<style>
	.header-row {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		margin: 1rem 0 1.5rem;
	}
</style>
