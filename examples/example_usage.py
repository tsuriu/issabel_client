import os
import sys

# Add parent directory to path so we can import issabel_client without installing it
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from issabel_client import IssabelClient


def main():
    # --- Context manager usage (session is closed automatically on exit) ---
    with IssabelClient("your-pbx-ip", use_ssl=True, verify_ssl=False, timeout=30) as client:

        # 1. Authenticate
        print("Authenticating...")
        client.authenticate("admin", "your_password")
        print("Logged in successfully.")

        # 2. Check session state
        print("\nChecking auth status...")
        status = client.check_auth_status()
        print(f"Auth status: {status}")

        # 3. List all extensions
        print("\nFetching all extensions...")
        extensions = client.get_extensions()
        print(extensions)

        # 4. Create a single extension (with immediate reload — default)
        print("\nCreating extension 2000 with reload...")
        response = client.create_extensions({
            "extension": "2000",
            "name": "John Doe",
            "secret": "secret123",
        })
        print(f"Create response: {response}")

        # 5. Update an extension
        print("\nUpdating extension 2000...")
        response = client.update_extensions("2000", {"name": "John Doe Updated"})
        print(f"Update response: {response}")

        # 6. Search for an extension
        print("\nSearching for 'John' in extensions...")
        search_results = client.search("extensions", "John")
        print(f"Search results: {search_results}")

        # 7. Delete a single extension
        print("\nDeleting extension 2000...")
        response = client.delete_extensions("2000")
        print(f"Delete response: {response}")

        # 8. Delete multiple extensions at once
        print("\nDeleting extensions 2001, 2002 and 2003...")
        response = client.delete_resource("extensions", ["2001", "2002", "2003"])
        print(f"Bulk delete response: {response}")

        # ------------------------------------------------------------------
        # 9. Batch provisioning — create N extensions with ONE reload at the end
        # ------------------------------------------------------------------
        print("\nProvisioning 10 extensions in batch (single reload at the end)...")
        with client.batch():
            for ext_num in range(3000, 3010):
                client.create_extensions({
                    "extension": str(ext_num),
                    "name": f"Batch User {ext_num}",
                    "secret": "s3cr3t",
                })
                print(f"  Queued extension {ext_num} (no reload yet)")
        # manager/reload fires automatically here — Asterisk updated once.
        print("Batch complete — single reload dispatched.")

        # ------------------------------------------------------------------
        # 10. AMI wrapper — Asterisk Manager Interface
        # ------------------------------------------------------------------

        # Originate a call
        print("\nOriginating call SIP/1001 → 1002...")
        result = client.manager.originate(
            channel="SIP/1001",
            extension="1002",
            context="from-internal",
            priority=1,
        )
        print(f"Originate: {result}")

        # Queue status
        print("\nChecking queue 'support' status...")
        q_status = client.manager.queuestatus(queue="support")
        print(f"Queue status: {q_status}")

        # AstDB read/write
        print("\nWriting and reading an AstDB key...")
        client.manager.dbput(family="SDKTest", key="version", value="0.2.0")
        value = client.manager.dbget(family="SDKTest", key="version")
        print(f"AstDB value: {value}")

        # Manual Asterisk reload
        print("\nTriggering manual Asterisk reload...")
        reload_result = client.manager.reload()
        print(f"Reload result: {reload_result}")

        # ------------------------------------------------------------------
        # 11. Read-only resources — client raises before hitting the server
        # ------------------------------------------------------------------

        try:
            client.create_modules({"name": "test"})
        except NotImplementedError as e:
            print(f"\nCorrect: read-only guard triggered — {e}")

        # ------------------------------------------------------------------
        # 12. Ring Groups (dynamic method)
        # ------------------------------------------------------------------

        print("\nFetching all ring groups...")
        ring_groups = client.get_ringgroups()
        print(ring_groups)

        print("\nCreating a ring group...")
        rg_response = client.create_ringgroups({
            "description": "Sales",
            "strategy": "ringall",
            "ring_time": 20,
            "extension_list": ["1001", "1002"],
        })
        print(f"Ring group create: {rg_response}")


if __name__ == "__main__":
    main()
