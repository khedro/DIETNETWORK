<script lang="ts">
	import { api, ApiError } from '$lib/api';
	import Turnstile from '$lib/components/Turnstile.svelte';

	let email = '';
	let password = '';
	let consent = false;
	let captchaToken = '';
	let submitting = false;
	let error = '';
	let done = false;

	async function handleSubmit() {
		error = '';
		if (!captchaToken) {
			error = 'Please complete the CAPTCHA challenge.';
			return;
		}
		submitting = true;
		try {
			await api.signup(email, password, captchaToken, consent);
			done = true;
		} catch (e) {
			error = e instanceof ApiError ? e.message : 'Something went wrong. Please try again.';
		} finally {
			submitting = false;
		}
	}
</script>

<div class="form-wrap">
	<h1>Create your account</h1>

	{#if done}
		<div class="card">
			<p>
				Check <strong>{email}</strong> for a verification link. You must verify your email before
				you can log in or upload data.
			</p>
		</div>
	{:else}
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
					minlength="12"
					autocomplete="new-password"
				/>
				<p class="muted">At least 12 characters, with upper, lower, and a digit.</p>
			</div>

			<label class="checkbox">
				<input type="checkbox" bind:checked={consent} required />
				<span>
					I consent to the processing of my genetic data as described in the
					<a href="/privacy">privacy policy</a>, including 30-day automatic deletion.
				</span>
			</label>

			<Turnstile bind:token={captchaToken} />

			<button type="submit" disabled={submitting}>
				{submitting ? 'Creating account…' : 'Create account'}
			</button>

			<p class="muted">Already have an account? <a href="/login">Log in</a></p>
		</form>
	{/if}
</div>

<style>
	.form-wrap {
		max-width: 420px;
		margin: 0 auto;
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
