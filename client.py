import socket
import os
import sys
from urllib.parse import quote

class WebClient:
    def __init__(self, server_host='172.16.16.101', server_port=8885):
        self.server_host = server_host
        self.server_port = server_port
    
    def transmit_request(self, http_request):
        """Transmit HTTP request and retrieve response"""
        try:
            # Establish socket connection
            connection_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            connection_socket.connect((self.server_host, self.server_port))
            
            # Transmit request
            connection_socket.send(http_request.encode())
            
            # Collect response
            server_response = b""
            while True:
                received_chunk = connection_socket.recv(4096)
                if not received_chunk:
                    break
                server_response += received_chunk
                # Verify complete response received
                if b'\r\n\r\n' in server_response:
                    break
            
            connection_socket.close()
            return server_response.decode('utf-8', errors='ignore')
            
        except Exception as connection_error:
            return f"Error: {str(connection_error)}"
    
    def retrieve_file_listing(self):
        """Fetch directory listing from server"""
        http_request = "GET /files HTTP/1.0\r\n\r\n"
        server_response = self.transmit_request(http_request)
        
        # Parse HTML content from response
        if "200 OK" in server_response:
            html_start_pos = server_response.find('<html>')
            if html_start_pos != -1:
                html_body = server_response[html_start_pos:]
                # Basic parsing to extract file information
                print("\n=== Directory Contents ===")
                if '<tr>' in html_body:
                    table_rows = html_body.split('<tr>')
                    for table_row in table_rows[2:]:  # Skip header rows
                        if '<td>' in table_row:
                            table_cells = table_row.split('<td>')
                            if len(table_cells) >= 4:
                                file_name = table_cells[1].split('</td>')[0]
                                file_size = table_cells[2].split('</td>')[0]
                                last_modified = table_cells[3].split('</td>')[0]
                                print(f"File: {file_name} | Size: {file_size} bytes | Modified: {last_modified}")
                else:
                    print("Directory is empty")
            else:
                print("Unable to parse directory listing")
        else:
            print("Failed to retrieve directory listing")
            print(server_response)
    
    def transfer_file(self, file_path):
        """Transfer a file to the server"""
        if not os.path.exists(file_path):
            print(f"Error: File {file_path} does not exist")
            return
        
        file_name = os.path.basename(file_path)
        
        try:
            # Load file content
            with open(file_path, 'rb') as file_handle:
                file_data = file_handle.read()
            
            # Construct multipart form data
            form_boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
            
            # Assemble multipart body
            form_sections = []
            form_sections.append(f"------WebKitFormBoundary7MA4YWxkTrZu0gW")
            form_sections.append(f'Content-Disposition: form-data; name="file"; filename="{file_name}"')
            form_sections.append("Content-Type: application/octet-stream")
            form_sections.append("")
            
            # Combine headers
            header_section = "\r\n".join(form_sections) + "\r\n"
            
            # Assemble complete body
            complete_body = header_section.encode() + file_data + f"\r\n------WebKitFormBoundary7MA4YWxkTrZu0gW--\r\n".encode()
            
            # Construct HTTP request
            request_headers = [
                "POST /upload HTTP/1.0",
                f"Content-Type: multipart/form-data; boundary=----WebKitFormBoundary7MA4YWxkTrZu0gW",
                f"Content-Length: {len(complete_body)}",
                "",
                ""
            ]
            
            request_header_text = "\r\n".join(request_headers)
            full_request = request_header_text.encode() + complete_body
            
            # Transmit request via socket for binary data
            upload_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            upload_socket.connect((self.server_host, self.server_port))
            upload_socket.send(full_request)
            
            # Collect response
            upload_response = b""
            while True:
                response_chunk = upload_socket.recv(4096)
                if not response_chunk:
                    break
                upload_response += response_chunk
                if b'\r\n\r\n' in upload_response:
                    break
            
            upload_socket.close()
            
            response_text = upload_response.decode('utf-8', errors='ignore')
            if "200 OK" in response_text:
                print(f"Upload successful for {file_name}")
            else:
                print(f"Upload failed for {file_name}")
                print(response_text)
                
        except Exception as upload_error:
            print(f"Error during file upload: {str(upload_error)}")
    
    def remove_file(self, target_filename):
        """Remove a file from the server"""
        # Encode filename for URL to handle special characters
        encoded_name = quote(target_filename)
        delete_request = f"DELETE /delete/{encoded_name} HTTP/1.0\r\n\r\n"
        
        delete_response = self.transmit_request(delete_request)
        
        if "200 OK" in delete_response:
            print(f"File {target_filename} deleted successfully")
        elif "404 Not Found" in delete_response:
            print(f"File {target_filename} was not found")
        else:
            print(f"Failed to delete {target_filename}")
            print(delete_response)

def execute_main():
    print("=== HTTP File Management Client ===")
    print("Ensure your HTTP server is running on 172.16.16.101:8885")
    
    # Collect server connection details
    server_host = "172.16.16.101"
    server_port = 8885
    
    web_client = WebClient(server_host, server_port)
    
    while True:
        print("\n=== Available Options ===")
        print("1. List Files")
        print("2. Upload new file")
        print("3. Delete File")
        print("4. Exit application")
        
        user_choice = input("\nSelect option (1-4): ").strip()
        
        if user_choice == '1':
            print("Retrieving file directory...")
            web_client.retrieve_file_listing()
            
        elif user_choice == '2':
            file_location = input("Enter file path for upload: ").strip()
            if file_location:
                print(f"Uploading file {file_location}...")
                web_client.transfer_file(file_location)
            else:
                print("File path is required")
                
        elif user_choice == '3':
            # Display current server files first
            print("Files currently on server:")
            web_client.retrieve_file_listing()
            
            target_file = input("\nEnter filename to remove: ").strip()
            if target_file:
                confirmation = input(f"Confirm deletion of '{target_file}'? (y/N): ").strip().lower()
                if confirmation == 'y':
                    print(f"Removing file {target_file}...")
                    web_client.remove_file(target_file)
                else:
                    print("Deletion cancelled")
            else:
                print("Filename is required")
                
        elif user_choice == '4':
            print("Application terminated!")
            break
            
        else:
            print("Invalid selection. Please choose 1-4.")

if __name__ == "__main__":
    execute_main()