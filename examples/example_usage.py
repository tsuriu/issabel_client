import os
import sys

# Add parent directory to path so we can import issabel_client without installing it
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from issabel_client import IssabelClient


def main():
    # Initialize the client
    # Replace with your Issabel server IP/Hostname
    client = IssabelClient("localhost", use_ssl=False, verify_ssl=False)

    try:
        # 1. Authenticate
        print("Authenticating...")
        client.authenticate("admin", "admin")
        print("Logged in successfully (simulated)")

        # 2. List Extensions
        print("\nFetching all extensions...")
        extensions = client.get_extensions()
        print(extensions)

        # 3. Create a new extension
        print("\nCreating a new extension...")
        new_ext_data = {
            "name": "John Doe",
            "extension": "2000",
            "secret": "secret123"
        }
        response = client.create_extensions(new_ext_data)
        print(f"Create response: {response}")

        # 4. Update an extension
        print("\nUpdating extension 2000...")
        update_data = {
            "name": "John Doe Updated"
        }
        response = client.update_extensions("2000", update_data)
        print(f"Update response: {response}")

        # 5. Search for an extension
        print("\nSearching for 'John' in extensions...")
        search_results = client.search("extensions", "John")
        print(f"Search results: {search_results}")

        # 6. Delete an extension
        print("\nDeleting extension 2000...")
        response = client.delete_extensions("2000")
        print(f"Delete response: {response}")

        # 7. List Ring Groups (using dynamic method)
        # print("\nFetching all ring groups...")
        # ring_groups = client.get_ringgroups()
        # print(ring_groups)

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
