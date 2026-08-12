<script lang="ts">
	import { user } from '$lib/stores/auth';
</script>

<div class="hero">
	<h1>Genetic ancestry inference, powered by Diet Network</h1>
	<p class="muted">
		Upload your VCF or bgen genotype file and get ancestry predictions from HussinLab's pretrained
		Diet Network ensemble — 15 models trained on 1000 Genomes, covering 24 populations.
	</p>
	<div class="cta">
		{#if $user}
			<a href="/upload" class="btn">Start a new analysis</a>
		{:else}
			<a href="/signup" class="btn">Create a free account</a>
			<a href="/login" class="btn btn-secondary">Log in</a>
		{/if}
	</div>
</div>

<div class="grid">
	<div class="card">
		<h3>Bring your own genotypes</h3>
		<p class="muted">
			Accepts .vcf, .vcf.gz, and .bgen (with a .sample file). Genotypes must be harmonized to
			<strong>GRCh38</strong>.
		</p>
	</div>
	<div class="card">
		<h3>Async, ensemble inference</h3>
		<p class="muted">
			Each job runs 15 models sequentially — typically a few minutes. Track status live from your
			dashboard and get an email when results are ready.
		</p>
	</div>
	<div class="card">
		<h3>Privacy by design</h3>
		<p class="muted">
			Raw genotype files are deleted immediately after inference succeeds. All results
			auto-delete after 30 days. See our <a href="/privacy">privacy policy</a>.
		</p>
	</div>
</div>

<style>
	.hero {
		max-width: 640px;
		margin-bottom: 2.5rem;
	}
	h1 {
		font-size: 2rem;
		line-height: 1.2;
		margin-bottom: 0.75rem;
	}
	.cta {
		display: flex;
		gap: 0.75rem;
		margin-top: 1.5rem;
	}
	.grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
		gap: 1.25rem;
	}
	.grid h3 {
		margin-top: 0;
	}
</style>
