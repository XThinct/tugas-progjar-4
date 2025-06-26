from socket import *
import socket
import time
import sys
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from http import HttpServer

# Inisialisasi instance httpserver bersama (thread-safe karena thread berbagi memori)
shared_http_server = HttpServer()

# Lock untuk output yang thread-safe
output_lock = threading.Lock()

def print_with_timestamp(message, level="INFO"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    thread_id = threading.current_thread().ident
    
    with output_lock:
        if level == "INFO":
            print(f"[{timestamp}] [{thread_id:>8}] {message}")
        elif level == "SUCCESS":
            print(f"[{timestamp}] [{thread_id:>8}] {message}")
        elif level == "ERROR":
            print(f"[{timestamp}] [{thread_id:>8}] {message}")
        elif level == "WARNING":
            print(f"[{timestamp}] [{thread_id:>8}] {message}")
        elif level == "SERVER":
            print(f"[{timestamp}] [{'SERVER':>8}] {message}")
        elif level == "CLIENT":
            print(f"[{timestamp}] [{thread_id:>8}] {message}")

def ProcessClientInThread(client_socket, client_address):
    """Menangani permintaan klien dalam thread terpisah"""
    try:
        print_with_timestamp(f"Memproses klien {client_address[0]}:{client_address[1]}", "CLIENT")
        
        data_buffer = ""
        while True:
            try:
                received_bytes = client_socket.recv(4096)  # Buffer yang diperbesar untuk upload
                if received_bytes:
                    # Mengubah bytes menjadi string untuk penanganan request
                    request_text = received_bytes.decode('utf-8', errors='ignore')  # Menangani data binary dengan baik
                    data_buffer = data_buffer + request_text
                    
                    # Mendeteksi request HTTP yang lengkap
                    if '\r\n\r\n' in data_buffer:
                        # Ekstrak method dan path untuk logging
                        first_line = data_buffer.split('\r\n')[0]
                        method_path = first_line.split(' ')[:2] if len(first_line.split(' ')) >= 2 else ['UNKNOWN', '/']
                        
                        print_with_timestamp(f"{client_address[0]}:{client_address[1]} → {method_path[0]} {method_path[1]}", "INFO")
                        
                        # Request HTTP lengkap diterima, proses
                        http_response = shared_http_server.proses(data_buffer)
                        client_socket.sendall(http_response)
                        
                        print_with_timestamp(f"Response dikirim ke {client_address[0]}:{client_address[1]}", "SUCCESS")
                        break
                    elif data_buffer.endswith('\r\n') and ('GET' in data_buffer or 'POST' in data_buffer or 'DELETE' in data_buffer) and 'HTTP' in data_buffer:
                        # Ekstrak method dan path untuk logging
                        first_line = data_buffer.split('\r\n')[0]
                        method_path = first_line.split(' ')[:2] if len(first_line.split(' ')) >= 2 else ['UNKNOWN', '/']
                        
                        print_with_timestamp(f"{client_address[0]}:{client_address[1]} → {method_path[0]} {method_path[1]}", "INFO")
                        
                        # Menangani request sederhana (seperti GET /files)
                        http_response = shared_http_server.proses(data_buffer)
                        client_socket.sendall(http_response)
                        
                        print_with_timestamp(f"Response dikirim ke {client_address[0]}:{client_address[1]}", "SUCCESS")
                        break
                else:
                    # Koneksi ditutup oleh klien
                    print_with_timestamp(f"Koneksi ditutup oleh {client_address[0]}:{client_address[1]}", "WARNING")
                    break
            except OSError as network_error:
                print_with_timestamp(f"Error koneksi dengan {client_address[0]}:{client_address[1]}: {network_error}", "ERROR")
                break
        
        client_socket.close()
        print_with_timestamp(f"Selesai menangani {client_address[0]}:{client_address[1]}", "SUCCESS")
        return f"Berhasil menangani {client_address[0]}:{client_address[1]}"
        
    except Exception as process_error:
        print_with_timestamp(f"Error dalam ProcessClientInThread untuk {client_address[0]}:{client_address[1]}: {process_error}", "ERROR")
        if client_socket:
            client_socket.close()
        return f"Error menangani {client_address[0]}:{client_address[1]}: {str(process_error)}"

def print_server_status(active_threads):
    """Menampilkan status server secara berkala"""
    with output_lock:
        print(f"\n{'='*60}")
        print(f"SERVER STATUS - {datetime.now().strftime('%H:%M:%S')}")
        print(f"Active Threads: {active_threads}")
        print(f"Listening on: 172.16.16.101:8885")
        print(f"{'='*60}\n")

def LaunchServer():
    print_with_timestamp("Menginisialisasi Thread Pool HTTP Server...", "SERVER")
    
    # Inisialisasi socket server
    main_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    main_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    main_socket.bind(('172.16.16.101', 8885))
    main_socket.listen(10)
    
    print_with_timestamp("Thread Pool HTTP Server aktif di port 8885", "SERVER")
    print_with_timestamp(f"Main Thread ID: {threading.current_thread().ident}", "SERVER")
    
    # Melacak future thread yang aktif
    active_futures = []
    last_status_time = time.time()
    
    with ThreadPoolExecutor(max_workers=20) as executor:
        try:
            while True:
                # Menampilkan status server setiap 30 detik jika ada aktivitas
                current_time = time.time()
                if current_time - last_status_time > 30 and active_futures:
                    print_server_status(len(active_futures))
                    last_status_time = current_time
                
                # Menerima koneksi yang masuk
                connection, address = main_socket.accept()
                print_with_timestamp(f"Koneksi baru diterima dari {address[0]}:{address[1]}", "SERVER")
                
                # Menghapus future yang sudah selesai dari tracking
                completed_futures = [future for future in active_futures if future.done()]
                for done_future in completed_futures:
                    try:
                        result = done_future.result()
                        # Hasil sudah di-log di ProcessClientInThread, tidak perlu log lagi
                    except Exception as error:
                        print_with_timestamp(f"Task thread gagal: {error}", "ERROR")
                    active_futures.remove(done_future)
                
                # Menambahkan task penanganan klien baru ke thread pool
                future_task = executor.submit(ProcessClientInThread, connection, address)
                active_futures.append(future_task)
                
                print_with_timestamp(f"Thread aktif: {len(active_futures)}", "INFO")
                
        except KeyboardInterrupt:
            print_with_timestamp("Sinyal interrupt diterima. Mematikan server...", "WARNING")
            print_with_timestamp("Tekan Ctrl+C lagi untuk force shutdown", "WARNING")
            
            # Membiarkan thread aktif untuk selesai
            if active_futures:
                print_with_timestamp(f"Menunggu {len(active_futures)} thread aktif untuk selesai...", "INFO")
                try:
                    for done_future in as_completed(active_futures, timeout=10):
                        try:
                            final_result = done_future.result()
                            # Hasil sudah di-log di ProcessClientInThread
                        except Exception as final_error:
                            print_with_timestamp(f"Error thread: {final_error}", "ERROR")
                except TimeoutError:
                    print_with_timestamp("Timeout menunggu thread selesai, force shutdown", "WARNING")
                        
        except Exception as server_error:
            print_with_timestamp(f"Error server terjadi: {server_error}", "ERROR")
            
        finally:
            print_with_timestamp("Menutup socket server...", "SERVER")
            main_socket.close()
            print_with_timestamp("Server telah dimatikan dengan aman", "SERVER")
            
            # Footer penutup
            print("\n" + "="*60)
            print("HTTP Thread Pool Server - STOPPED")
            print("Terima kasih telah menggunakan server ini!")
            print("="*60)

def start_application():
    LaunchServer()

if __name__ == "__main__":
    start_application()