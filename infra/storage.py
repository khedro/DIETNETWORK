"""Encrypted Cinder volume for user data (uploads/results) + Postgres.
`volume_type` must name an encrypted type available in your Arbutus
project (`openstack volume type list`) -- Arbutus commonly offers a
LUKS-encrypted type; ask your project's Alliance support contact if
unsure which name to use."""
import pulumi
import pulumi_openstack as openstack


def create_data_volume(config: pulumi.Config) -> openstack.blockstorage.Volume:
    return openstack.blockstorage.Volume(
        "dietnet-data-volume",
        name="dietnet-data",
        description="Encrypted volume: per-user uploads/results + Postgres data (30-day retention)",
        size=config.get_int("volumeSizeGb") or 150,
        volume_type=config.require("volumeType"),
    )
