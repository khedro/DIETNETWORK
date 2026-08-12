<script lang="ts">
	import '../app.css';
	import { onMount } from 'svelte';
	import { user, loadUser, logout } from '$lib/stores/auth';
	import { goto } from '$app/navigation';

	onMount(loadUser);

	async function handleLogout() {
		await logout();
		goto('/login');
	}
</script>

<header>
	<div class="container nav">
		<a href="/" class="brand">🧬 Diet Network Ancestry</a>
		<nav>
			{#if $user}
				<a href="/dashboard">Dashboard</a>
				<a href="/upload">New analysis</a>
				<button class="btn-secondary" on:click={handleLogout}>Log out</button>
			{:else}
				<a href="/login">Log in</a>
				<a href="/signup" class="btn">Sign up</a>
			{/if}
		</nav>
	</div>
</header>

<main class="container">
	<slot />
</main>

<footer class="container">
	<p class="muted">
		Research tool — inference only, not a diagnostic or clinical service. See our
		<a href="/privacy">privacy &amp; data retention policy</a>.
	</p>
</footer>

<style>
	header {
		border-bottom: 1px solid var(--border);
		background: var(--surface);
	}
	.nav {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 1rem 1.5rem;
	}
	.brand {
		font-weight: 700;
		font-size: 1.1rem;
		color: var(--text);
		text-decoration: none;
	}
	nav {
		display: flex;
		align-items: center;
		gap: 1rem;
	}
	main {
		padding: 2.5rem 1.5rem 4rem;
		min-height: 60vh;
	}
	footer {
		padding: 1.5rem;
		border-top: 1px solid var(--border);
	}
</style>
