<script lang="ts">
	import { api, ApiError } from '$lib/api';
	import { user } from '$lib/stores/auth';
	import Turnstile from '$lib/components/Turnstile.svelte';
	import { goto } from '$app/navigation';

	let email = '';
	let password = '';
	let captchaToken = '';
	let submitting = false;
	let error = '';

	async function handleSubmit() {
		error = '';
		if (!captchaToken) {
			error = 'Please complete the CAPTCHA challenge.';
			return;
		}
		submitting = true;
		try {
			const loggedInUser = await api.login(email, password, captchaToken);
			user.set(loggedInUser);
			goto('/dashboard');
		} catch (e) {
			error = e instanceof ApiError ? e.message : 'Something went wrong. Please try again.';
		} finally {
			submitting = false;
		}
	}
</script>

<div class="form-wrap">
	<h1>Log in</h1>

	<form class="card stack" on:submit|preventDefault={handleSubmit}>
		{#if error}<div class="error-banner">{error}</div>{/if}

		<div>
			<label for="email">Email</label>
			<input id="email" type="email" bind:value={email} required autocomplete="email" />
		</div>

		<div>
			<label for="password">Password</label>
			<input
				id="password"
				type="password"
				bind:value={password}
				required
				autocomplete="current-password"
			/>
		</div>

		<Turnstile bind:token={captchaToken} />

		<button type="submit" disabled={submitting}>{submitting ? 'Logging in…' : 'Log in'}</button>

		<p class="muted">Don't have an account? <a href="/signup">Sign up</a></p>
	</form>
</div>

<style>
	.form-wrap {
		max-width: 420px;
		margin: 0 auto;
	}
</style>
