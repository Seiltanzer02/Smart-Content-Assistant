import React from 'react';
import { Box, Flex, Spinner, Text } from '@chakra-ui/react';

interface LoadingIndicatorProps {
  message?: string;
  isFullPage?: boolean;
}

const LoadingIndicator: React.FC<LoadingIndicatorProps> = ({ 
  message = 'Загрузка...', 
  isFullPage = false 
}) => {
  if (isFullPage) {
    return (
      <Flex 
        position="fixed"
        top="0"
        left="0"
        right="0"
        bottom="0"
        zIndex="9999"
        backgroundColor="rgba(0, 0, 0, 0.7)"
        justifyContent="center"
        alignItems="center"
        flexDirection="column"
      >
        <Box 
          p={6} 
          borderRadius="md" 
          bg="white" 
          boxShadow="xl" 
          textAlign="center"
        >
          <Spinner
            thickness="4px"
            speed="0.65s"
            emptyColor="gray.200"
            color="blue.500"
            size="xl"
            mb={4}
          />
          <Text fontSize="lg" fontWeight="bold" color="gray.800">{message}</Text>
        </Box>
      </Flex>
    );
  }

  return (
    <Flex alignItems="center" justifyContent="center" p={4}>
      <Spinner
        thickness="4px"
        speed="0.65s"
        emptyColor="gray.200"
        color="blue.500"
        size="md"
        mr={3}
      />
      <Text>{message}</Text>
    </Flex>
  );
};

export default LoadingIndicator; 