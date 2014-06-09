from tornado.httpclient import AsyncHTTPClient, HTTPClient
from tornado.httputil import url_concat
from lxml import objectify
import json
import hashlib
from core import AWSRequest


class SQS(object):
    def __init__(self, access_key, secret_key, region, async=True):
        self.region = region
        self.__access_key = access_key
        self.__secret_key = secret_key
        self._http = AsyncHTTPClient() if async else HTTPClient()
        self.service = 'sqs'
        self.common_params = {
            "Version": "2012-11-05",
        }

    @staticmethod
    def parse(response):
        """
        Accepts XML response from AWS and converts it to common Python objects.

        As Python 2 has no "yield from" syntax, all async methods for AWS API
        have to return Futures. After yielding in coroutine they become
        Tornado Response objects containing raw XML body returned by AWS.
        This method helps you to avoid manual response parsing, it accepts
        response object, detects its type and casts it to common Python object
        like dict, list or string. Typical usage will be::

            response = yield sqs.send_message(queue, text)
            # response.body has raw XML from AWS API
            message_id = sqs.parse(response)
            # now response is parsed and message_id has a normal Python string.

        :param response: raw response from AWS
        :return: Response values converted to common Python objects
        """
        def _parse_GetQueueAttributesResult(root):
            """helper to parse get_queue_attributes response"""
            result = {}
            for attr in root.GetQueueAttributesResult.Attribute:
                result[str(attr.Name)] = str(attr.Value)
            return result

        def _parse_ReceiveMessageResult(root):
            """helper to parse SQS message XML"""
            if root.ReceiveMessageResult == '':
                return None
            message = root.ReceiveMessageResult.Message
            result = {
                'Body': message.Body.text,
                'MD5OfBody': message.MD5OfBody.text,
                'ReceiptHandle': message.ReceiptHandle.text,
                'Attributes': {}
            }
            for attr in message.Attribute:
                result['Attributes'][str(attr.Name)] = attr.Value.text
            return result

        response_mapping = {
            'CreateQueueResult': lambda x: str(x.CreateQueueResult.QueueUrl),
            'GetQueueAttributesResult': _parse_GetQueueAttributesResult,
            'ReceiveMessageResult': _parse_ReceiveMessageResult,
        }
        root = objectify.fromstring(response.body)
        for key, extract_func in response_mapping.items():
            if hasattr(root, key):
                return extract_func(root)
        return None

    def listen_queue(self, queue_uri, wait_time=15, max_messages=1,
                     visibility_timeout=300):
        """
        Retrieves one or more messages from the specified queue.
        Long poll support is enabled by using the WaitTimeSeconds parameter.
        AWS API: ReceiveMessage_

        :param queue_uri: The URL of the Amazon SQS queue to take action on.
        :param wait_time: The duration (in seconds) for which the call will
            wait for a message to arrive in the queue before returning.
            If a message is available, the call will return sooner.
        :param max_messages: The maximum number of messages to return.
        :param visibility_timeout: The duration (in seconds) that the received
            messages are hidden from subsequent retrieve requests after being
            retrieved by a ReceiveMessage request.
        :return: A message or a list of messages.
        """
        params = {
            "Action": "ReceiveMessage",
            "WaitTimeSeconds": wait_time,
            "MaxNumberOfMessages": max_messages,
            "VisibilityTimeout": visibility_timeout,
            "AttributeName": "All",
        }
        params.update(self.common_params)
        full_url = url_concat(queue_uri, params)
        request = AWSRequest(full_url, service=self.service, region=self.region,
                             access_key=self.__access_key,
                             secret_key=self.__secret_key)
        return self._http.fetch(request)

    def send_message(self, queue_url, message_body):
        """
        Delivers a message to the specified queue.
        AWS API: SendMessage_

        :param queue_url: The URL of the Amazon SQS queue to take action on.
        :param message_body: The message to send. String maximum 256 KB in size.
        :return: MD5OfMessageAttributes, MD5OfMessageBody, MessageId
        """
        params = {
            "Action": "SendMessage",
            "MessageBody": message_body,
            }
        params.update(self.common_params)
        full_url = url_concat(queue_url, params)
        request = AWSRequest(full_url, service=self.service, region=self.region,
                             access_key=self.__access_key,
                             secret_key=self.__secret_key)
        return self._http.fetch(request)

    def delete_message(self, queue_url, receipt_handle):
        """
        Deletes the specified message from the specified queue.
        Specify the message by using the message's receipt handle, not ID.
        AWS API: DeleteMessage_

        :param queue_url: The URL of the Amazon SQS queue to take action on.
        :param receipt_handle: The receipt handle associated with the message.
        :return: Request ID
        """
        params = {
            "Action": "DeleteMessage",
            "ReceiptHandle": receipt_handle,
        }
        params.update(self.common_params)
        full_url = url_concat(queue_url, params)
        request = AWSRequest(full_url, service=self.service, region=self.region,
                             access_key=self.__access_key,
                             secret_key=self.__secret_key)
        return self._http.fetch(request)

    def create_queue(self, queue_name, attributes={}):
        """
        Creates a new queue, or returns the URL of an existing one.
        To successfully create a new queue, a name that is unique within
        the scope of own queues should be provided.
        AWS API: CreateQueue_

        :param queue_name: The name for the queue to be created.
        :return: QueueUrl - the URL for the created Amazon SQS queue.
        """
        params = {
            "Action": "CreateQueue",
            "QueueName": queue_name,
        }
        for i, (key, value) in enumerate(attributes):
            params['Attribute.%s.Name' % i] = key
            params['Attribute.%s.Value' % i] = value

        url = "http://{service}.{region}.amazonaws.com/".format(
            service=self.service, region=self.region)
        params.update(self.common_params)
        full_url = url_concat(url, params)
        request = AWSRequest(full_url, service=self.service, region=self.region,
                             access_key=self.__access_key,
                             secret_key=self.__secret_key)
        return self._http.fetch(request)

    def delete_queue(self, queue_url):
        """
        Deletes the queue specified by the queue URL, regardless of whether
        the queue is empty. If the specified queue does not exist, SQS
        returns a successful response.
        AWS API: DeleteQueue_

        :param queue_url: The URL of the Amazon SQS queue to take action on.
        :return: Request ID
        """
        params = {
            "Action": "DeleteQueue",
            }
        params.update(self.common_params)
        full_url = url_concat(queue_url, params)
        request = AWSRequest(full_url, service=self.service, region=self.region,
                             access_key=self.__access_key,
                             secret_key=self.__secret_key)
        return self._http.fetch(request)

    def get_queue_attributes(self, queue_url, attributes=('all',)):
        """
        Gets attributes for the specified queue.
        The following attributes are supported:
        All (returns all values), ApproximateNumberOfMessages,
        ApproximateNumberOfMessagesNotVisible,
        VisibilityTimeout, CreatedTimestamp, LastModifiedTimestamp, Policy,
        MaximumMessageSize, MessageRetentionPeriod, QueueArn,
        ApproximateNumberOfMessagesDelayed, DelaySeconds,
        ReceiveMessageWaitTimeSeconds, RedrivePolicy.
        AWS API: GetQueueAttributes_

        :param queue_url: The URL of the Amazon SQS queue to take action on.
        :param attributes: A list of attributes to retrieve, ['all'] by default.
        :return: A map of attributes to the respective values.
        """
        params = {
            "Action": "GetQueueAttributes",
            }
        for i, attr in enumerate(attributes):
            params['AttributeName.%s' % (i + 1)] = attr

        params.update(self.common_params)
        full_url = url_concat(queue_url, params)
        request = AWSRequest(full_url, service=self.service, region=self.region,
                             access_key=self.__access_key,
                             secret_key=self.__secret_key)
        return self._http.fetch(request)

    def set_queue_attributes(self, queue_url, attributes={}):
        """
        Sets the value of one or more queue attributes.
        AWS API: SetQueueAttributes_

        :param attributes: dict of attribute names and values.
        :param queue_url: The URL of the Amazon SQS queue to take action on.
        :return: Request ID
        """
        params = {
            "Action": "SetQueueAttributes",
        }
        for i, (key, value) in enumerate(attributes.items()):
            params['Attribute.Name'] = key
            params['Attribute.Value'] = value

        params.update(self.common_params)
        full_url = url_concat(queue_url, params)
        request = AWSRequest(full_url, service=self.service, region=self.region,
                             access_key=self.__access_key,
                             secret_key=self.__secret_key)
        return self._http.fetch(request, raise_error=False)
