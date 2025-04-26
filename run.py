# Main entry point for the TikTok Analyzer

import os
import sys
import logging
import argparse
import time
import csv
import boto3
import pandas as pd
from pathlib import Path
from typing import List, Dict, Optional
from botocore.exceptions import ClientError

from src.scraper.tiktok_scraper import TikTokScraper
from src.analyzer.age_gender_predictor import OptimizedMiVOLOAnalyzer
from src.utils.helpers import upload_to_s3, download_from_s3, read_csv, write_csv
from config.settings import (
    INPUT_DIR, OUTPUT_DIR, S3_BUCKET, SQS_QUEUE_URL, BATCH_SIZE
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TikTokAnalyzerApp:
    """Main application for TikTok Age/Gender Analyzer"""
    
    def __init__(self, use_cloud: bool = False):
        """Initialize the TikTok Analyzer application
        
        Args:
            use_cloud: Whether to use cloud services (S3, SQS)
        """
        self.use_cloud = use_cloud
        
        # Initialize cloud clients if using cloud
        if self.use_cloud:
            self.s3_client = boto3.client('s3')
            if SQS_QUEUE_URL:
                self.sqs_client = boto3.client('sqs')
            self.cloudwatch_client = boto3.client('cloudwatch')
        
        # Initialize components
        logger.info("Initializing scraper and analyzer components...")
        self.scraper = TikTokScraper(output_dir=INPUT_DIR)
        self.analyzer = OptimizedMiVOLOAnalyzer(batch_size=BATCH_SIZE)
        
        logger.info("TikTok Analyzer application initialized")
    
    def report_metric(self, metric_name: str, value: float) -> None:
        """Report a custom metric to CloudWatch
        
        Args:
            metric_name: Name of the metric
            value: Value to report
        """
        if not self.use_cloud:
            return
            
        try:
            self.cloudwatch_client.put_metric_data(
                Namespace='TikTokAnalyzer',
                MetricData=[
                    {
                        'MetricName': metric_name,
                        'Value': value,
                        'Unit': 'Count'
                    }
                ]
            )
            logger.debug(f"Reported metric {metric_name}: {value}")
        except Exception as e:
            logger.warning(f"Failed to report metric {metric_name}: {str(e)}")
    
    def process_queue(self, max_messages: int = 10) -> int:
        """Process usernames from SQS queue
        
        Args:
            max_messages: Maximum number of messages to process
        
        Returns:
            Number of usernames processed
        """
        if not self.use_cloud or not SQS_QUEUE_URL:
            logger.error("Cannot process queue: Cloud mode disabled or SQS_QUEUE_URL not set")
            return 0
            
        start_time = time.time()
        processed_count = 0
        
        try:
            # Receive messages from queue
            response = self.sqs_client.receive_message(
                QueueUrl=SQS_QUEUE_URL,
                MaxNumberOfMessages=max_messages,
                WaitTimeSeconds=10
            )
            
            messages = response.get('Messages', [])
            logger.info(f"Received {len(messages)} messages from queue")
            
            for message in messages:
                # Extract username and process
                try:
                    username = message['Body']
                    logger.info(f"Processing username from queue: {username}")
                    
                    # Process username
                    self.process_username(username)
                    processed_count += 1
                    
                    # Delete message from queue
                    self.sqs_client.delete_message(
                        QueueUrl=SQS_QUEUE_URL,
                        ReceiptHandle=message['ReceiptHandle']
                    )
                except Exception as e:
                    logger.error(f"Error processing username {username} from queue: {str(e)}")
                    self.report_metric('ErrorCount', 1)
            
            # Report metrics
            processing_time = time.time() - start_time
            self.report_metric('ProcessedUsernames', processed_count)
            self.report_metric('ProcessingTime', processing_time)
            
            logger.info(f"Processed {processed_count} usernames in {processing_time:.2f} seconds")
            return processed_count
            
        except Exception as e:
            logger.error(f"Error processing queue: {str(e)}")
            self.report_metric('ErrorCount', 1)
            return 0
    
    def process_username(self, username: str) -> Optional[Dict]:
        """Process a single username
        
        Args:
            username: TikTok username to process
        
        Returns:
            Result dictionary or None if processing failed
        """
        try:
            logger.info(f"Processing username: {username}")
            
            # Step 1: Scrape thumbnails
            start_time = time.time()
            thumbnails = self.scraper.scrape_user_thumbnails(username)
            scrape_time = time.time() - start_time
            logger.info(f"Scraped {len(thumbnails)} thumbnails for {username} in {scrape_time:.2f} seconds")
            
            if not thumbnails:
                logger.warning(f"No thumbnails found for {username}")
                return None
            
            # Step 2: Analyze thumbnails
            start_time = time.time()
            avg_age, gender = self.analyzer.process_thumbnails(thumbnails, username)
            analyze_time = time.time() - start_time
            logger.info(f"Analyzed thumbnails for {username} in {analyze_time:.2f} seconds")
            
            if avg_age is None or gender is None:
                logger.warning(f"Could not determine age/gender for {username}")
                return None
            
            # Step 3: Save result
            result = {
                'username': username,
                'age': round(avg_age, 1),
                'gender': gender
            }
            
            # Save individual result to file
            user_output_dir = OUTPUT_DIR / username
            user_output_dir.mkdir(exist_ok=True, parents=True)
            result_path = user_output_dir / 'result.csv'
            
            write_csv([result], result_path, ['username', 'age', 'gender'])
            
            # Upload to S3 if in cloud mode
            if self.use_cloud:
                s3_key = f"output/{username}/result.csv"
                upload_to_s3(result_path, S3_BUCKET, s3_key)
            
            logger.info(f"Completed processing for {username}: Age={avg_age:.1f}, Gender={gender}")
            return result
            
        except Exception as e:
            logger.error(f"Error processing username {username}: {str(e)}")
            self.report_metric('ErrorCount', 1)
            return None
    
    def process_file(self, input_file: Path, output_file: Optional[Path] = None) -> List[Dict]:
        """Process usernames from a CSV file
        
        Args:
            input_file: Path to input CSV file with usernames
            output_file: Path to output CSV file for results
        
        Returns:
            List of result dictionaries
        """
        if output_file is None:
            output_file = OUTPUT_DIR / f"results_{int(time.time())}.csv"
        
        try:
            # Read usernames from CSV
            if self.use_cloud and not input_file.exists():
                # Try to download from S3
                s3_key = f"input/{input_file.name}"
                download_from_s3(S3_BUCKET, s3_key, input_file)
            
            if not input_file.exists():
                raise FileNotFoundError(f"Input file not found: {input_file}")
            
            # Read usernames
            df = pd.read_csv(input_file, encoding='utf-16')
            
            if 'username' not in df.columns:
                raise ValueError("Input CSV must have a 'username' column")
            
            usernames = df['username'].tolist()
            logger.info(f"Read {len(usernames)} usernames from {input_file}")
            
            # Process each username
            results = []
            for i, username in enumerate(usernames):
                logger.info(f"Processing {i+1}/{len(usernames)}: {username}")
                result = self.process_username(username)
                if result:
                    results.append(result)
                
                # Add a small delay between usernames
                if i < len(usernames) - 1:
                    time.sleep(1)
            
            # Save results to CSV
            if results:
                write_csv(results, output_file, ['username', 'age', 'gender'])
                logger.info(f"Saved {len(results)} results to {output_file}")
                
                # Upload to S3 if in cloud mode
                if self.use_cloud:
                    s3_key = f"output/{output_file.name}"
                    upload_to_s3(output_file, S3_BUCKET, s3_key)
            else:
                logger.warning("No results to save")
            
            return results
            
        except Exception as e:
            logger.error(f"Error processing file {input_file}: {str(e)}")
            self.report_metric('ErrorCount', 1)
            return []
    
    def run(self, mode: str = 'file', input_file: Optional[str] = None, output_file: Optional[str] = None) -> int:
        """Run the application in the specified mode
        
        Args:
            mode: Processing mode ('file' or 'queue')
            input_file: Path to input CSV file (for 'file' mode)
            output_file: Path to output CSV file (for 'file' mode)
        
        Returns:
            Number of usernames processed
        """
        start_time = time.time()
        
        try:
            if mode == 'queue':
                processed_count = self.process_queue()
            elif mode == 'file':
                if not input_file:
                    raise ValueError("Input file required for 'file' mode")
                    
                input_path = Path(input_file)
                output_path = Path(output_file) if output_file else None
                
                results = self.process_file(input_path, output_path)
                processed_count = len(results)
            else:
                logger.error(f"Unknown mode: {mode}")
                return 0
            
            total_time = time.time() - start_time
            logger.info(f"Total processing time: {total_time:.2f} seconds")
            logger.info(f"Processed {processed_count} usernames")
            
            return processed_count
            
        except Exception as e:
            logger.error(f"Error running application: {str(e)}")
            return 0

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='TikTok Age/Gender Analyzer')
    parser.add_argument('--mode', choices=['queue', 'file'], default='file', help='Processing mode')
    parser.add_argument('--cloud', action='store_true', help='Use cloud services (S3, SQS)')
    parser.add_argument('--input', help='Input CSV file path (for file mode)')
    parser.add_argument('--output', help='Output CSV file path (for file mode)')
    args = parser.parse_args()
    
    app = TikTokAnalyzerApp(use_cloud=args.cloud)
    result = app.run(mode=args.mode, input_file=args.input, output_file=args.output)
    
    sys.exit(0 if result > 0 else 1)
