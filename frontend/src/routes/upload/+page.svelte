<script lang="ts">
	import { api, ApiError } from '$lib/api';
	import { goto } from '$app/navigation';

	const MAX_MB = 512;
	const GENOTYPE_EXTENSIONS = ['.vcf', '.vcf.gz', '.bgen'];

	let genotypeFile: File | null = null;
	let sampleFile: File | null = null;
	let consent = false;
	let dragOver = false;
	let submitting = false;
	let error = '';

	$: isBgen = genotypeFile?.name.toLowerCase().endsWith('.bgen') ?? false;

	function validateGenotypeFile(file: File): string | null {
		const name = file.name.toLowerCase();
		if (!GENOTYPE_EXTENSIONS.some((ext) => name.endsWith(ext))) {
			return 'Unsupported file type. Please upload a .vcf, .vcf.gz, or .bgen file.';
		}
		if (file.size > MAX_MB * 1024 * 1024) {
			return `File exceeds the ${MAX_MB} MB upload limit.`;
		}
		return null;
	}

	function handleFiles(files: FileList | null) {
		error = '';
		if (!files || files.length === 0) return;
		const file = files[0];
		const validationError = validateGenotypeFile(file);
		if (validationError) {
			error = validationError;
			genotypeFile = null;
			return;
		}
		genotypeFile = file;
		if (!file.name.toLowerCase().endsWith('.bgen')) sampleFile = null;
	}

	function onDrop(e: DragEvent) {
		e.preventDefault();
		dragOver = false;
		handleFiles(e.dataTransfer?.files ?? null);
	}

	async function handleSubmit() {
		error = '';
		if (!genotypeFile) {
			error = 'Please choose a genotype file.';
			return;
		}
		if (isBgen && !sampleFile) {
			error = 'A .sample file is required alongside a .bgen upload.';
			return;
		}
		if (!consent) {
			error = 'You must consent to processing before uploading.';
			return;
		}
		submitting = true;
		try {
			const job = await api.upload(genotypeFile, consent, sampleFile ?? undefined);
			goto(`/jobs/${job.id}`);
		} catch (e) {
			error = e instanceof ApiError ? e.message : 'Upload failed. Please try again.';
		} finally {
			submitting = false;
		}
	}
</script>

<div class="form-wrap">
	<h1>New ancestry analysis</h1>
	<p class="muted">
		Genotypes must be harmonized to <strong>GRCh38</strong>. The platform cannot re-map genome
		builds — mismatched builds will show as a very low SNP overlap.
	</p>

	<form class="card stack" on:submit|preventDefault={handleSubmit}>
		{#if error}<div class="error-banner">{error}</div>{/if}

		<div
			class="dropzone"
			class:drag={dragOver}
			role="button"
			tabindex="0"
			on:dragover|preventDefault={() => (dragOver = true)}
			on:dragleave={() => (dragOver = false)}
			on:drop={onDrop}
		>
			{#if genotypeFile}
				<p><strong>{genotypeFile.name}</strong></p>
				<p class="muted">{(genotypeFile.size / (1024 * 1024)).toFixed(1)} MB</p>
			{:else}
				<p>Drag &amp; drop your .vcf, .vcf.gz, or .bgen file here</p>
				<p class="muted">or</p>
			{/if}
			<label class="btn-secondary file-btn">
				Browse files
				<input
					type="file"
					accept=".vcf,.vcf.gz,.bgen"
					on:change={(e) => handleFiles(e.currentTarget.files)}
					hidden
				/>
			</label>
			<p class="muted">Max {MAX_MB} MB</p>
		</div>

		{#if isBgen}
			<div>
				<label for="sample">Sample file (.sample)</label>
				<input
					id="sample"
					type="file"
					accept=".sample"
					on:change={(e) => (sampleFile = e.currentTarget.files?.[0] ?? null)}
					required
				/>
				<p class="muted">Required to convert bgen genotypes to PLINK format.</p>
			</div>
		{/if}

		<label class="checkbox">
			<input type="checkbox" bind:checked={consent} required />
			<span>
				I consent to processing this genetic data for ancestry inference, per the
				<a href="/privacy">privacy policy</a>. I understand the raw file is deleted immediately
				after successful inference, and derived results auto-delete after 30 days.
			</span>
		</label>

		<button type="submit" disabled={submitting}>
			{submitting ? 'Uploading…' : 'Run ancestry inference'}
		</button>
	</form>
</div>

<style>
	.form-wrap {
		max-width: 560px;
		margin: 0 auto;
	}
	.dropzone {
		border: 2px dashed var(--border);
		border-radius: var(--radius);
		padding: 2rem 1rem;
		text-align: center;
		transition: border-color 0.15s ease, background 0.15s ease;
	}
	.dropzone.drag {
		border-color: var(--primary);
		background: #eff6ff;
	}
	.file-btn {
		display: inline-block;
		margin-top: 0.5rem;
		cursor: pointer;
	}
	.checkbox {
		display: flex;
		align-items: flex-start;
		gap: 0.5rem;
		font-weight: 400;
		font-size: 0.9rem;
	}
	.checkbox input {
		margin-top: 0.2rem;
	}
</style>
