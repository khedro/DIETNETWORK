<script lang="ts">
	import { page } from '$app/stores';
	import { onMount } from 'svelte';
	import { api, ApiError } from '$lib/api';

	let status: 'checking' | 'ok' | 'error' = 'checking';
	let message = '';

	onMount(async () => {
		const token = $page.url.searchParams.get('token');
		if (!token) {
			status = 'error';
			message = 'Missing verification token.';
			return;
		}
		try {
			await api.verifyEmail(token);
			status = 'ok';
		} catch (e) {
			status = 'error';
			message = e instanceof ApiError ? e.message : 'Verification failed.';
		}
	});
</script>

<div class="form-wrap card">
	{#if status === 'checking'}
		<p>Verifying your email…</p>
	{:else if status === 'ok'}
		<h2>Email verified 🎉</h2>
		<p class="muted">You can now <a href="/login">log in</a> and start an analysis.</p>
	{:else}
		<h2>Verification failed</h2>
		<p class="error-banner">{message}</p>
		<p class="muted">The link may have expired. Try signing up again to request a new one.</p>
	{/if}
</div>

<style>
	.form-wrap {
		max-width: 420px;
		margin: 0 auto;
		text-align: center;
	}
</style>
